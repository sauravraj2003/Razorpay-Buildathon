import os
import sys
import json
import re

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import Dict, Any, List
from agents.llm_client import get_groq_llm
from graph.runner import process_message, get_or_create_session, SESSION_STORE
from tools.cart_ops import calculate_cart_totals

JUDGE_PROMPT_TEMPLATE = """You are an expert impartial judge evaluating an autonomous multi-agent e-commerce platform.

Scenario Details:
- Name: {scenario_name}
- Target Agent: {target_agent}
- User Message: "{input_message}"
- Initial Cart: {initial_cart}
- Expected Intent: {expected_intent}
- Expected Action: {expected_action}
- Judge Criteria: {judge_criteria}

Actual Execution:
- Detected Intent: {actual_intent}
- Active Agent: {actual_agent}
- HITL Pending: {hitl_pending}
- Payment Status: {payment_status}
- Agent Output: {agent_output}
- Response Message: "{response_message}"

Evaluate and score each of the following 4 dimensions on a scale of 1 to 5:
1. correctness (1-5): Did the agent perform the requested task accurately?
2. groundedness (1-5): Did the agent stay strictly grounded to real catalog data with zero hallucinations?
3. tool_appropriateness (1-5): Were database search, cart ops, or Razorpay payment tools invoked appropriately?
4. state_integrity (1-5): Did the agent preserve shared state without corruption?

Output strictly JSON format:
{{
  "correctness": 5,
  "groundedness": 5,
  "tool_appropriateness": 5,
  "state_integrity": 5,
  "passed": true,
  "critique": "brief one-line summary of reasoning"
}}
"""

def evaluate_with_heuristic(scenario: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic rule-based judge to ensure consistent evaluation even without API keys."""
    actual_intent = state.get("intent")
    actual_agent = state.get("last_agent")
    target_agent = scenario.get("target_agent")
    expected_intent = scenario.get("expected_intent")
    expected_action = scenario.get("expected_action")
    agent_output = state.get("agent_output") or {}

    correctness = 5
    groundedness = 5
    tool_app = 5
    state_int = 5
    passed = True
    critique = "Execution satisfies all behavioral benchmarks."

    # Specific Scenario Verifications:
    if expected_action == "fallback_no_match":
        # Non-existent query must report fallback
        if not agent_output.get("fallback"):
            correctness = 2
            groundedness = 1
            passed = False
            critique = "Buyer hallucinated instead of reporting fallback for non-existent product."
        else:
            critique = "Buyer correctly reported catalog fallback with zero hallucination."

    elif expected_action == "cart_validation_error":
        # 0 items in cart must be rejected
        if state.get("payment_status") == "link_created" or state.get("hitl_pending"):
            correctness = 1
            tool_app = 2
            passed = False
            critique = "Checkout initiated payment on an empty cart."
        else:
            critique = "Checkout successfully rejected empty cart with error."

    elif expected_action == "surface_hitl_approval":
        # Valid checkout must surface HITL
        if not state.get("hitl_pending"):
            correctness = 2
            passed = False
            critique = "Checkout did not request HITL approval before payment."
        else:
            critique = "Checkout properly calculated GST and requested HITL approval."

    elif expected_action == "create_razorpay_link":
        if state.get("payment_status") != "link_created":
            correctness = 2
            passed = False
            critique = "Razorpay payment link was not created upon confirmation."
        else:
            critique = "Razorpay link generated with valid payment url."

    elif expected_action == "suppress_upsell":
        # Upsell mid-checkout must be suppressed
        if agent_output.get("action") != "upsell_suppressed":
            correctness = 2
            passed = False
            critique = "Upsell interrupted active checkout flow violating timing accuracy."
        else:
            critique = "Upsell agent correctly suppressed offers during active checkout."

    elif expected_action == "recommend_max_2_complementary":
        offers = agent_output.get("offers", [])
        if len(offers) > 2 or len(offers) == 0:
            correctness = 3
            passed = False
            critique = f"Upsell returned {len(offers)} offers, expected 1 or 2 complementary items."
        else:
            critique = f"Upsell returned {len(offers)} complementary items with relevance justifications."

    elif expected_action == "classify_gateway_error":
        err_type = (state.get("error_context") or {}).get("error_type")
        if err_type != "gateway_error":
            correctness = 2
            passed = False
            critique = "Failed to classify gateway error."
        else:
            critique = "Successfully classified error as gateway_error and requested user consent."

    elif expected_intent != actual_intent and expected_intent != "confirm_payment":
        correctness = 3
        critique = f"Intent misclassified: expected '{expected_intent}', got '{actual_intent}'."

    return {
        "correctness": correctness,
        "groundedness": groundedness,
        "tool_appropriateness": tool_app,
        "state_integrity": state_int,
        "passed": passed,
        "critique": critique
    }

def run_evaluation_suite() -> Dict[str, Any]:
    """Runs all 20 scenarios, computes LLM-as-a-judge scores, and aggregates metrics."""
    scenarios_path = os.path.join(os.path.dirname(__file__), "scenarios.json")
    with open(scenarios_path, "r") as f:
        scenarios = json.load(f)

    llm = get_groq_llm(temperature=0.0)

    scenario_results = []
    total_passed = 0
    reasoning_scores = []

    # Per-Agent metric counters
    buyer_queries = 0
    buyer_relevant = 0
    buyer_fallback_queries = 0
    buyer_fallback_success = 0

    checkout_initiated = 0
    checkout_completed = 0
    checkout_errors = 0
    checkout_recovered = 0

    upsell_triggers = 0
    upsell_timing_correct = 0

    orchestrator_routes = 0
    orchestrator_routes_correct = 0
    orchestrator_handoffs = 0
    orchestrator_handoffs_complete = 0

    for sc in scenarios:
        session_id = f"eval_{sc['id']}"
        initial_cart = sc.get("initial_cart", [])

        # Setup initial state
        session_state = get_or_create_session(session_id)
        session_state["cart"] = [dict(i) for i in initial_cart]
        if "state_override" in sc:
            for k, v in sc["state_override"].items():
                session_state[k] = v

        # Process message
        res_state = process_message(
            session_id=session_id,
            message=sc["input_message"],
            override_cart=session_state["cart"]
        )

        # Judge evaluation
        judge_score = None
        if llm:
            try:
                prompt = JUDGE_PROMPT_TEMPLATE.format(
                    scenario_name=sc["name"],
                    target_agent=sc["target_agent"],
                    input_message=sc["input_message"],
                    initial_cart=json.dumps(initial_cart),
                    expected_intent=sc["expected_intent"],
                    expected_action=sc["expected_action"],
                    judge_criteria=sc["judge_criteria"],
                    actual_intent=res_state.get("intent"),
                    actual_agent=res_state.get("last_agent"),
                    hitl_pending=res_state.get("hitl_pending"),
                    payment_status=res_state.get("payment_status"),
                    agent_output=json.dumps(res_state.get("agent_output")),
                    response_message=res_state.get("response_message", "")
                )
                eval_response = llm.invoke(prompt)
                content = eval_response.content.strip()
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    judge_score = json.loads(json_match.group(0))
            except Exception:
                judge_score = None

        if not judge_score or "correctness" not in judge_score:
            judge_score = evaluate_with_heuristic(sc, res_state)

        passed = judge_score.get("passed", True)
        if passed:
            total_passed += 1

        avg_dim_score = (
            judge_score.get("correctness", 5) +
            judge_score.get("groundedness", 5) +
            judge_score.get("tool_appropriateness", 5) +
            judge_score.get("state_integrity", 5)
        ) / 4.0
        reasoning_scores.append(avg_dim_score)

        # Track per-agent metrics
        # 1. Buyer
        if sc["target_agent"] == "buyer":
            buyer_queries += 1
            if passed:
                buyer_relevant += 1
            if sc["expected_action"] == "fallback_no_match":
                buyer_fallback_queries += 1
                if res_state.get("agent_output", {}).get("fallback"):
                    buyer_fallback_success += 1

        # 2. Checkout
        if sc["target_agent"] == "checkout":
            if sc["expected_action"] == "create_razorpay_link":
                checkout_initiated += 1
                if res_state.get("payment_status") == "link_created":
                    checkout_completed += 1
            if sc["expected_action"] == "classify_gateway_error":
                checkout_errors += 1
                if res_state.get("payment_status") == "failed" and (res_state.get("error_context") or {}).get("error_type") == "gateway_error":
                    checkout_recovered += 1

        # 3. Upsell
        if sc["target_agent"] == "upsell":
            upsell_triggers += 1
            if passed:
                upsell_timing_correct += 1

        # 4. Orchestrator
        orchestrator_routes += 1
        if res_state.get("intent") == sc["expected_intent"]:
            orchestrator_routes_correct += 1
        if res_state.get("handoff_context") and "cart_snapshot" in res_state["handoff_context"]:
            orchestrator_handoffs_complete += 1

        scenario_results.append({
            "id": sc["id"],
            "name": sc["name"],
            "agent": res_state.get("last_agent"),
            "intent": res_state.get("intent"),
            "passed": passed,
            "score": round(avg_dim_score, 2),
            "critique": judge_score.get("critique", "")
        })

    # Aggregated metrics
    total_scenarios = len(scenarios)
    pass_rate = round((total_passed / total_scenarios) * 100, 1)
    avg_reasoning = round(sum(reasoning_scores) / len(reasoning_scores), 2)
    overall_score = int(round((pass_rate * 0.5) + (avg_reasoning / 5.0 * 50)))

    buyer_precision = round((buyer_relevant / max(1, buyer_queries)) * 100, 1)
    buyer_fallback_rate = round((buyer_fallback_success / max(1, buyer_fallback_queries)) * 100, 1)
    checkout_completion = round((checkout_completed / max(1, checkout_initiated)) * 100, 1) if checkout_initiated else 100.0
    upsell_timing = round((upsell_timing_correct / max(1, upsell_triggers)) * 100, 1)
    routing_acc = round((orchestrator_routes_correct / max(1, orchestrator_routes)) * 100, 1)

    return {
        "total_scenarios": total_scenarios,
        "passed_scenarios": total_passed,
        "pass_rate": pass_rate,
        "avg_reasoning_score": avg_reasoning,
        "overall_score": overall_score,
        "buyer_precision": buyer_precision,
        "buyer_fallback_rate": buyer_fallback_rate,
        "checkout_completion": checkout_completion,
        "upsell_timing_accuracy": upsell_timing,
        "routing_accuracy": routing_acc,
        "scenarios": scenario_results
    }

if __name__ == "__main__":
    report = run_evaluation_suite()
    print("=" * 60)
    print(f"EVALUATION COMPLETE: {report['passed_scenarios']}/{report['total_scenarios']} passed ({report['pass_rate']}%)")
    print(f"Overall Benchmark Score: {report['overall_score']}/100 | Avg Judge Score: {report['avg_reasoning_score']}/5.0")
    print(f"Buyer Retrieval Precision: {report['buyer_precision']}% | Fallback Rate: {report['buyer_fallback_rate']}%")
    print(f"Checkout Completion: {report['checkout_completion']}%")
    print(f"Upsell Timing Accuracy: {report['upsell_timing_accuracy']}%")
    print(f"Orchestrator Routing Accuracy: {report['routing_accuracy']}%")
    print("=" * 60)
