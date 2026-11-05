"""FastAPI Backend for Multi-Agent Agentic Commerce Platform."""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from tools.db import init_db, get_all_products, get_product_by_id, get_connection
from tools.cart_ops import add_to_cart, remove_from_cart, calculate_cart_totals
from graph.runner import process_message, approve_hitl, get_or_create_session, SESSION_STORE

# Initialize database on startup
init_db()

app = FastAPI(
    title="Multi-Agent Agentic Commerce Platform",
    description="Autonomous commerce agents built on LangGraph, Groq, Razorpay, and SQLite.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request / Response Schemas
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    user_id: str = "user_guest"
    override_cart: Optional[List[Dict[str, Any]]] = None

class HitlApprovalRequest(BaseModel):
    session_id: str
    approved: bool

class CartItemRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = 1

# API Endpoints
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "agents": ["orchestrator", "buyer", "checkout", "upsell"],
        "active_sessions": len(SESSION_STORE)
    }

@app.get("/products")
def list_products():
    """Retrieve all available catalog products."""
    products = get_all_products()
    return {"count": len(products), "products": products}

@app.get("/products/{product_id}")
def get_product(product_id: str):
    """Retrieve single product details."""
    p = get_product_by_id(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p

@app.get("/session/{session_id}")
def get_session_state(session_id: str):
    """Fetch raw state for session."""
    state = get_or_create_session(session_id)
    return state

@app.post("/cart/add")
def add_item_to_cart(req: CartItemRequest):
    """Directly add item to cart for a given session."""
    state = get_or_create_session(req.session_id)
    updated_cart, msg = add_to_cart(state.get("cart", []), req.product_id, req.quantity)
    state["cart"] = updated_cart
    return {
        "success": True,
        "message": msg,
        "cart": updated_cart,
        "totals": calculate_cart_totals(updated_cart)
    }

@app.post("/cart/remove")
def remove_item_from_cart(req: CartItemRequest):
    """Remove item from cart for a given session."""
    state = get_or_create_session(req.session_id)
    updated_cart, msg = remove_from_cart(state.get("cart", []), req.product_id)
    state["cart"] = updated_cart
    return {
        "success": True,
        "message": msg,
        "cart": updated_cart,
        "totals": calculate_cart_totals(updated_cart)
    }

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    """
    Primary multi-agent conversation endpoint:
    Routes message through Orchestrator -> Buyer/Checkout/Upsell -> StateGraph.
    """
    try:
        updated_state = process_message(
            session_id=req.session_id,
            message=req.message,
            user_id=req.user_id,
            override_cart=req.override_cart
        )
        return {
            "session_id": req.session_id,
            "response": updated_state.get("response_message", ""),
            "last_agent": updated_state.get("last_agent", "orchestrator"),
            "intent": updated_state.get("intent", "unknown"),
            "hitl_pending": updated_state.get("hitl_pending", False),
            "payment_status": updated_state.get("payment_status", "idle"),
            "payment_details": updated_state.get("payment_details"),
            "cart": updated_state.get("cart", []),
            "cart_totals": calculate_cart_totals(updated_state.get("cart", [])),
            "agent_output": updated_state.get("agent_output"),
            "messages": updated_state.get("messages", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_streaming_endpoint(req: ChatRequest):
    """
    Streaming chat endpoint emitting SSE chunks for real-time thought & token streaming.
    """
    async def event_generator():
        # Emit routing step
        yield f"data: {json.dumps({'type': 'status', 'step': 'Orchestrator classifying intent...'})}\n\n"
        await asyncio.sleep(0.1)

        updated_state = process_message(
            session_id=req.session_id,
            message=req.message,
            user_id=req.user_id,
            override_cart=req.override_cart
        )

        agent = updated_state.get("last_agent", "orchestrator")
        yield f"data: {json.dumps({'type': 'status', 'step': f'Dispatched to {agent.upper()} Agent'})}\n\n"
        await asyncio.sleep(0.1)

        # Stream response tokens
        full_text = updated_state.get("response_message", "")
        chunk_size = 25
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            await asyncio.sleep(0.02)

        # Stream final state payload
        final_payload = {
            "type": "done",
            "session_id": req.session_id,
            "last_agent": agent,
            "intent": updated_state.get("intent"),
            "hitl_pending": updated_state.get("hitl_pending", False),
            "payment_status": updated_state.get("payment_status", "idle"),
            "payment_details": updated_state.get("payment_details"),
            "cart": updated_state.get("cart", []),
            "cart_totals": calculate_cart_totals(updated_state.get("cart", [])),
            "agent_output": updated_state.get("agent_output")
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/chat/approve")
def hitl_approval_endpoint(req: HitlApprovalRequest):
    """
    Human-in-the-Loop decision endpoint:
    Allows user to approve or cancel pending actions (e.g. Razorpay payment link generation).
    """
    result = approve_hitl(session_id=req.session_id, approved=req.approved)
    state = result.get("state", {})
    return {
        "success": result.get("success"),
        "approved": req.approved,
        "response": state.get("response_message", ""),
        "last_agent": state.get("last_agent"),
        "payment_status": state.get("payment_status"),
        "payment_details": state.get("payment_details"),
        "cart": state.get("cart", [])
    }

@app.get("/orders")
def list_orders():
    """Retrieve all logged orders from SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    orders = []
    for r in rows:
        item = dict(r)
        item["items"] = json.loads(item["items"])
        orders.append(item)
    return {"count": len(orders), "orders": orders}

@app.post("/eval/run")
def run_eval_endpoint():
    """Execute evaluation harness and return the benchmark results."""
    from eval.harness import run_evaluation_suite
    results = run_evaluation_suite()
    return results

@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serve the interactive web demonstration interface."""
    html_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r") as f:
            return f.read()
    return "<h1>Multi-Agent Agentic Commerce Backend Running!</h1>"
