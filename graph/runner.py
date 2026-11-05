"""Session execution runner for LangGraph Commerce StateGraph."""
from typing import Dict, Any, Optional
from graph.graph import commerce_graph
from graph.state import AgenticCommerceState

# In-memory session state store for fast lookup and state preservation
SESSION_STORE: Dict[str, AgenticCommerceState] = {}

def get_or_create_session(session_id: str, user_id: str = "user_default") -> AgenticCommerceState:
    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = {
            "user_id": user_id,
            "session_id": session_id,
            "intent": "unknown",
            "cart": [],
            "last_agent": "orchestrator",
            "agent_output": None,
            "hitl_pending": False,
            "payment_status": "idle",
            "upsell_shown": False,
            "upsell_declined": False,
            "messages": [],
            "error_context": None,
            "payment_details": None,
            "handoff_context": None,
            "current_input": "",
            "response_message": ""
        }
    return SESSION_STORE[session_id]

def process_message(
    session_id: str,
    message: str,
    user_id: str = "user_default",
    override_cart: Optional[list] = None
) -> Dict[str, Any]:
    """Runs a message through the LangGraph agent network and updates state."""
    state = get_or_create_session(session_id, user_id)
    
    if override_cart is not None:
        state["cart"] = override_cart

    state["current_input"] = message
    state["messages"].append({
        "role": "user",
        "content": message
    })

    # Thread config for checkpointer
    config = {"configurable": {"thread_id": session_id}}

    # Invoke graph
    updated_state = commerce_graph.invoke(state, config=config)

    # Append assistant response to messages
    if updated_state.get("response_message"):
        updated_state["messages"].append({
            "role": "assistant",
            "content": updated_state["response_message"],
            "agent": updated_state.get("last_agent", "orchestrator")
        })

    # Save to session store
    SESSION_STORE[session_id] = updated_state
    return updated_state

def approve_hitl(session_id: str, approved: bool) -> Dict[str, Any]:
    """Handles explicit Human-in-the-Loop decision."""
    state = get_or_create_session(session_id)
    if not state.get("hitl_pending"):
        return {
            "success": False,
            "message": "No action is currently pending human approval for this session.",
            "state": state
        }
    
    action_msg = "Yes, proceed with payment" if approved else "No, cancel payment"
    result = process_message(session_id=session_id, message=action_msg, user_id=state.get("user_id", "user_default"))
    return {
        "success": True,
        "approved": approved,
        "state": result
    }
