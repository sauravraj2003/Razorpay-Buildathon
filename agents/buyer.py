"""Buyer Agent: Performs catalog search, ranks top 3 results with 1-line justification, and avoids hallucination."""
import json
import re
from typing import Dict, Any, List
from agents.llm_client import get_groq_llm
from graph.state import AgenticCommerceState, RankedProduct
from tools.catalog_search import search_catalog

BUYER_SYSTEM_PROMPT = """You are the Buyer Agent for an autonomous e-commerce platform.
Your job is catalog search and product recommendation.

Rules:
1. Always return ranked results (top 3), not just one.
2. Justify each recommendation in ONE concise line explaining why it fits the query.
3. If no good match exists in the provided catalog candidates, say so explicitly — DO NOT hallucinate products.
4. Output MUST be strictly valid JSON matching this schema:
{
  "fallback": false,
  "results": [
    {
      "product_id": "string",
      "name": "string",
      "price": 0.0,
      "reason": "one line justification",
      "confidence": 0.95
    }
  ]
}

If no candidate matches, output:
{
  "fallback": true,
  "results": [],
  "message": "No matching products found in the catalog."
}
"""

def buyer_node(state: AgenticCommerceState) -> Dict[str, Any]:
    """Buyer Agent node execution."""
    query = state.get("current_input", "")
    
    # Query database search tool
    candidate_matches = search_catalog(query=query, limit=3)
    
    # Anti-hallucination check: if search tool returns no results above confidence threshold
    if not candidate_matches:
        fallback_output = {
            "fallback": True,
            "results": [],
            "message": f"I couldn't find any products in our catalog matching '{query}'. We currently stock smartphones, laptops, audio gear, and tech accessories."
        }
        return {
            "last_agent": "buyer",
            "agent_output": fallback_output,
            "response_message": fallback_output["message"]
        }

    llm = get_groq_llm(temperature=0.1)
    ranked_results: List[RankedProduct] = []

    if llm:
        try:
            candidates_json = json.dumps([
                {
                    "id": m["product"]["id"],
                    "name": m["product"]["name"],
                    "price": m["product"]["price"],
                    "category": m["product"]["category"],
                    "description": m["product"]["description"],
                    "confidence": m["confidence"]
                }
                for m in candidate_matches
            ])
            prompt = f"{BUYER_SYSTEM_PROMPT}\nUser Query: {query}\nCatalog Candidates:\n{candidates_json}"
            response = llm.invoke(prompt)
            content = response.content.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                if not parsed.get("fallback") and parsed.get("results"):
                    ranked_results = parsed["results"]
        except Exception:
            ranked_results = []

    # Deterministic fallback reasoning if LLM is unavailable or fails to format
    if not ranked_results:
        for idx, item in enumerate(candidate_matches):
            p = item["product"]
            conf = item["confidence"]
            # 1-line justification based on product attributes and query
            rank_label = "Top recommendation" if idx == 0 else ("Alternative choice" if idx == 1 else "Budget/value option")
            reason = f"{rank_label}: {p['name']} features {p['category'].lower()} specs ({p['description'][:60]}...)."
            ranked_results.append({
                "product_id": p["id"],
                "name": p["name"],
                "price": float(p["price"]),
                "reason": reason,
                "confidence": float(conf)
            })

    # Build user-facing response
    lines = [f"Here are the top matches for '{query}':\n"]
    for i, r in enumerate(ranked_results, 1):
        lines.append(f"{i}. **{r['name']}** — ₹{r['price']:,.2f}")
        lines.append(f"   *Why:* {r['reason']}")
        lines.append(f"   *ID:* `{r['product_id']}` (Match confidence: {int(r['confidence'] * 100)}%)\n")

    lines.append("Would you like to add any of these to your cart or proceed to checkout?")
    formatted_msg = "\n".join(lines)

    agent_output = {
        "fallback": False,
        "results": ranked_results
    }

    return {
        "last_agent": "buyer",
        "agent_output": agent_output,
        "response_message": formatted_msg
    }
