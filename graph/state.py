"""State definitions for the Multi-Agent Agentic Commerce Platform."""
from typing import TypedDict, List, Dict, Any, Optional

class ProductItem(TypedDict):
    product_id: str
    name: str
    price: float
    quantity: int
    category: str

class RankedProduct(TypedDict):
    product_id: str
    name: str
    price: float
    reason: str
    confidence: float

class AgenticCommerceState(TypedDict, total=False):
    # Core state attributes required by the spec
    user_id: str
    session_id: str
    intent: str  # search, checkout, upsell, chit_chat, confirm_payment, decline_upsell, help, unknown
    cart: List[Dict[str, Any]]  # [{product_id, name, price, quantity, category}]
    last_agent: str  # orchestrator, buyer, checkout, upsell
    agent_output: Optional[Dict[str, Any]]  # structured response from the agent
    hitl_pending: bool  # True when human approval is required before action
    payment_status: str  # idle, pending_approval, link_created, paid, failed, cancelled
    upsell_shown: bool  # True if upsell was shown in this session

    # Conversational memory & execution metadata
    messages: List[Dict[str, str]]  # [{"role": "user"|"assistant"|"system", "content": str, "agent": str}]
    upsell_declined: bool  # True if user actively declined an upsell
    error_context: Optional[Dict[str, Any]]  # Error details (e.g. gateway error, cart validation)
    payment_details: Optional[Dict[str, Any]]  # Razorpay payment link ID, url, amount, etc.
    handoff_context: Optional[Dict[str, Any]]  # Context payload passed during agent handoff
    current_input: str  # Latest message from user
    response_message: str  # Final text message to return to user
