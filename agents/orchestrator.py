"""Orchestrator Agent: Routes intents and manages state handoffs."""
import json
import re
from typing import Dict, Any
from agents.llm_client import get_groq_llm
from graph.state import AgenticCommerceState

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator for an autonomous commerce platform.
Your job is: Route, not reason. Classify intent and dispatch — do not attempt to fulfill requests yourself.

Key instruction: "Do not attempt to answer product or pricing questions. Your only job is to decide which agent handles this and what context they need."

Available Agents:
1. 'buyer': Catalog search, product recommendations, product inquiries, searching by category/specs/price.
2. 'checkout': User wants to buy, proceed to payment, view/validate cart for purchase, or complete order.
3. 'upsell': User asks for matching accessories or recommendations directly related to items already in the cart.
4. 'chit_chat': Greetings, help questions, general conversation that does not require catalog search or buying.

Output JSON format ONLY:
{
  "intent": "search" | "checkout" | "confirm_payment" | "decline_upsell" | "upsell" | "chit_chat",
  "target_agent": "buyer" | "checkout" | "upsell" | "orchestrator",
  "reasoning": "brief justification for routing",
  "hitl_required": boolean (true if user is asking to finalize a transaction/payment)
}
"""

def word_match(keywords: list, text: str) -> bool:
    """Checks if any keyword matches as a distinct word or phrase in text."""
    for kw in keywords:
        if " " in kw:
            if kw in text:
                return True
        else:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                return True
    return False

def classify_intent_heuristic(message: str, state: AgenticCommerceState) -> Dict[str, Any]:
    """Deterministic intent classifier fallback for fast, 100% grounded routing."""
    msg = message.lower().strip()
    
    # Check for HITL payment confirmations
    if state.get("hitl_pending") or state.get("payment_status") == "pending_approval":
        if word_match(["no", "cancel", "stop", "abort", "reject", "don't", "dont"], msg):
            return {
                "intent": "cancel_payment",
                "target_agent": "checkout",
                "reasoning": "User aborted payment during HITL pending state.",
                "hitl_required": False
            }
        elif word_match(["yes", "confirm", "proceed", "pay", "approve", "ok", "sure", "continue"], msg):
            return {
                "intent": "confirm_payment",
                "target_agent": "checkout",
                "reasoning": "User confirmed payment during HITL pending state.",
                "hitl_required": False
            }

    # Check for upsell decline signals
    if state.get("upsell_shown") and word_match(["no", "skip", "no thanks", "no upsell", "don't want", "dont want", "pass", "just checkout"], msg):
        return {
            "intent": "decline_upsell",
            "target_agent": "checkout" if "checkout" in msg else "orchestrator",
            "reasoning": "User explicitly declined upsell offer.",
            "hitl_required": False
        }

    # Checkout signals
    if word_match(["checkout", "proceed to buy", "pay", "payment", "buy now", "place order", "purchase", "finalize", "transaction"], msg):
        return {
            "intent": "checkout",
            "target_agent": "checkout",
            "reasoning": "User is requesting checkout or inquiring about payment/transaction.",
            "hitl_required": True
        }

    # Upsell signals (matching accessories, add-ons, bundles for cart items)
    if word_match(["accessories", "matching", "complement", "add-on", "upsell", "bundle"], msg):
        return {
            "intent": "upsell",
            "target_agent": "upsell",
            "reasoning": "User requested complementary accessories or add-ons.",
            "hitl_required": False
        }

    # Search signals
    if word_match(["find", "search", "show", "looking for", "phone", "laptop", "headphone", "earbuds", "watch", "keyboard", "mouse", "charger", "case", "recommend", "price", "buy a", "buy an"], msg):
        # Edge case: multi-intent message ("find X and buy Y")
        if "and buy" in msg or "and checkout" in msg:
            return {
                "intent": "search",
                "target_agent": "buyer",
                "reasoning": "Multi-intent detected: routing first to buyer to fulfill item retrieval.",
                "hitl_required": False
            }
        return {
            "intent": "search",
            "target_agent": "buyer",
            "reasoning": "User wants product discovery/catalog search.",
            "hitl_required": False
        }

    # Chit-chat & Greetings
    return {
        "intent": "chit_chat",
        "target_agent": "orchestrator",
        "reasoning": "General conversation or greeting.",
        "hitl_required": False
    }

def orchestrator_node(state: AgenticCommerceState) -> Dict[str, Any]:
    """
    Orchestrator node:
    - Identifies which agent owns the intent
    - Passes full context (cart state, user history, last agent output)
    - Triggers HITL when needed
    """
    user_input = state.get("current_input", "")
    llm = get_groq_llm(temperature=0.0)
    
    routing_decision = None
    if llm:
        try:
            cart_summary = json.dumps(state.get("cart", []))
            prompt = f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\nCurrent Cart: {cart_summary}\nLast Agent: {state.get('last_agent')}\nHITL Pending: {state.get('hitl_pending')}\nUser Message: {user_input}"
            response = llm.invoke(prompt)
            content = response.content.strip()
            # Extract JSON block
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                routing_decision = json.loads(json_match.group(0))
        except Exception:
            routing_decision = None

    if not routing_decision or "target_agent" not in routing_decision:
        routing_decision = classify_intent_heuristic(user_input, state)

    # Pass full context with every handoff
    handoff_context = {
        "cart_snapshot": state.get("cart", []),
        "cart_item_count": sum(i.get("quantity", 1) for i in state.get("cart", [])),
        "user_history_count": len(state.get("messages", [])),
        "last_agent": state.get("last_agent"),
        "last_agent_output": state.get("agent_output"),
        "upsell_shown": state.get("upsell_shown", False),
        "upsell_declined": state.get("upsell_declined", False),
        "hitl_pending": state.get("hitl_pending", False)
    }

    intent = routing_decision.get("intent", "search")
    target_agent = routing_decision.get("target_agent", "buyer")

    # If chit-chat or direct help
    response_msg = ""
    if target_agent == "orchestrator" or intent == "chit_chat":
        response_msg = "Hello! I am your AI Commerce Assistant. I can help you search our catalog (phones, laptops, headphones, wearables), manage your cart, and checkout securely with Razorpay. How can I help you today?"

    return {
        "intent": intent,
        "last_agent": "orchestrator",
        "handoff_context": handoff_context,
        "agent_output": {
            "routed_to": target_agent,
            "intent": intent,
            "reasoning": routing_decision.get("reasoning", "")
        },
        "response_message": response_msg if response_msg else state.get("response_message", "")
    }
