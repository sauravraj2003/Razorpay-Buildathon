"""Upsell Agent: Targets complementary products (max 2), respects decline signals, and guards against mid-checkout intrusion."""
import json
from typing import Dict, Any, List
from graph.state import AgenticCommerceState
from tools.db import get_product_by_id, get_all_products

def upsell_node(state: AgenticCommerceState) -> Dict[str, Any]:
    """
    Upsell Agent execution node:
    - Timing accuracy guard: Only triggers post-cart-confirmation, NEVER mid-checkout
    - Recommends at most 2 complementary items with relevance reasons
    - Respects 'no upsell' decline signals
    """
    cart = state.get("cart", [])
    upsell_shown = state.get("upsell_shown", False)
    upsell_declined = state.get("upsell_declined", False)
    hitl_pending = state.get("hitl_pending", False)
    payment_status = state.get("payment_status", "idle")
    current_input = state.get("current_input", "").lower()

    # 1. Handle explicit decline signals
    if any(phrase in current_input for phrase in ["no", "skip", "no thanks", "no upsell", "don't want", "dont want", "pass"]):
        return {
            "last_agent": "upsell",
            "upsell_declined": True,
            "agent_output": {
                "action": "upsell_declined",
                "message": "User declined upsell. Respecting preference."
            },
            "response_message": "Got it! No extra items added. We'll proceed with your current cart."
        }

    # 2. Timing Accuracy: Guard against triggering mid-checkout or when cart is empty
    if hitl_pending or payment_status in ["pending_approval", "link_created"]:
        return {
            "last_agent": "upsell",
            "agent_output": {
                "action": "upsell_suppressed",
                "reason": "Timing guard: cannot interrupt active checkout flow."
            },
            "response_message": state.get("response_message", "")
        }

    if not cart:
        return {
            "last_agent": "upsell",
            "agent_output": {
                "action": "upsell_suppressed",
                "reason": "Cart is empty."
            },
            "response_message": "Your cart is currently empty. Explore our catalog to find great devices!"
        }

    # 3. Respect previous decline or previous offer (don't annoy the user repeatedly)
    if upsell_declined or upsell_shown:
        return {
            "last_agent": "upsell",
            "agent_output": {
                "action": "upsell_skipped",
                "reason": "Upsell already displayed or declined once."
            },
            "response_message": state.get("response_message", "")
        }

    # 4. Find complementary products based on cart contents
    cart_product_ids = {item["product_id"] for item in cart}
    complementary_candidates = []

    for item in cart:
        prod = get_product_by_id(item["product_id"])
        if prod and "complementary_ids" in prod:
            for comp_id in prod["complementary_ids"]:
                if comp_id not in cart_product_ids and comp_id not in [c["id"] for c in complementary_candidates]:
                    comp_prod = get_product_by_id(comp_id)
                    if comp_prod and comp_prod["stock"] > 0:
                        complementary_candidates.append(comp_prod)

    # Fallback to high-rating accessories if no direct linked complementary items
    if not complementary_candidates:
        all_products = get_all_products()
        for p in all_products:
            if p["category"] == "Accessories" and p["id"] not in cart_product_ids:
                complementary_candidates.append(p)
                if len(complementary_candidates) >= 2:
                    break

    # Strictly limit to at most 2 complementary items
    selected_offers = complementary_candidates[:2]

    if not selected_offers:
        return {
            "last_agent": "upsell",
            "upsell_shown": True,
            "agent_output": {"action": "no_complementary_items_found", "offers": []},
            "response_message": "Your cart looks great! Ready to checkout whenever you are."
        }

    # Build curated 1-line relevance reasons
    upsell_items = []
    lines = ["✨ **Complementary Add-ons for your order:**\n"]
    for p in selected_offers:
        # Formulate complementary reason based on category
        reason = f"Perfect companion accessory for items in your cart to maximize protection & performance."
        if "Charger" in p["name"]:
            reason = "Recommended pairing: delivers ultra-fast GaN charging speeds for your new device."
        elif "Case" in p["name"] or "Sleeve" in p["name"]:
            reason = "Custom-fit protective gear to keep your investment pristine from day one."
        elif "Mouse" in p["name"] or "Keyboard" in p["name"]:
            reason = "Ergonomic enhancement tailored for your productivity setup."

        upsell_items.append({
            "product_id": p["id"],
            "name": p["name"],
            "price": p["price"],
            "reason": reason
        })
        lines.append(f"• **{p['name']}** (+₹{p['price']:,.2f})")
        lines.append(f"  *{reason}*\n")

    lines.append("Would you like to add either of these, or proceed directly to checkout?")

    return {
        "last_agent": "upsell",
        "upsell_shown": True,
        "agent_output": {
            "action": "upsell_offered",
            "offers": upsell_items
        },
        "response_message": "\n".join(lines)
    }
