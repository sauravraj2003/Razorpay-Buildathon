"""Conditional edge routing logic for Agentic Commerce."""
from typing import Literal
from graph.state import AgenticCommerceState

def route_from_orchestrator(state: AgenticCommerceState) -> Literal["buyer", "checkout", "upsell", "__end__"]:
    """Determines the downstream agent from the orchestrator's classified intent and state."""
    intent = state.get("intent", "search")
    hitl_pending = state.get("hitl_pending", False)

    if intent in ["confirm_payment", "cancel_payment"]:
        return "checkout"

    if intent == "checkout":
        return "checkout"

    if intent == "search":
        return "buyer"

    if intent in ["upsell", "decline_upsell"]:
        return "upsell"

    if intent == "chit_chat":
        return "__end__"

    # Default fallback
    return "buyer"
