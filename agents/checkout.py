"""Checkout Agent: Cart validation, Human-in-the-Loop approval, Razorpay link generation, and error classification."""
import json
from typing import Dict, Any
from graph.state import AgenticCommerceState
from tools.cart_ops import validate_cart, calculate_cart_totals
from tools.razorpay_tool import create_payment_link

def checkout_node(state: AgenticCommerceState) -> Dict[str, Any]:
    """
    Checkout Agent execution node:
    - Cart validation (0-items, stock checks)
    - HITL surfacing before payment
    - Razorpay payment link initiation
    - Error classification (user error vs. gateway error)
    - Zero retry without explicit confirmation
    """
    cart = state.get("cart", [])
    user_id = state.get("user_id", "user_guest")
    intent = state.get("intent", "checkout")
    user_input = state.get("current_input", "").lower()
    hitl_pending = state.get("hitl_pending", False)
    payment_status = state.get("payment_status", "idle")

    # 1. Edge Case: Validate cart state
    is_valid, validation_msg = validate_cart(cart)
    if not is_valid:
        return {
            "last_agent": "checkout",
            "hitl_pending": False,
            "payment_status": "failed",
            "error_context": {
                "error_type": "user_error",
                "message": validation_msg
            },
            "agent_output": {
                "action": "cart_validation_failed",
                "reason": validation_msg
            },
            "response_message": f"❌ Checkout cannot proceed: {validation_msg}"
        }

    totals = calculate_cart_totals(cart)
    items_summary = ", ".join([f"{item['quantity']}x {item['name']}" for item in cart])

    # 2. User Aborted / Cancelled Payment
    if intent == "cancel_payment" or ("no" in user_input and hitl_pending):
        return {
            "last_agent": "checkout",
            "hitl_pending": False,
            "payment_status": "cancelled",
            "agent_output": {
                "action": "payment_cancelled",
                "reason": "User declined payment approval."
            },
            "response_message": "Checkout was paused. Your cart remains saved. Let me know whenever you would like to proceed or modify your items."
        }

    # 3. User Confirmed Payment (HITL Approved)
    if intent == "confirm_payment" or (hitl_pending and any(w in user_input for w in ["yes", "confirm", "proceed", "pay", "ok", "sure"])):
        # Check if error simulation is requested (for eval testing)
        err_ctx = state.get("error_context") or {}
        simulate_error = "simulate_gateway_error" in user_input or err_ctx.get("simulate_gateway", False)

        payment_res = create_payment_link(
            amount=totals["total"],
            description=f"Order payment for {items_summary}",
            user_id=user_id,
            items=cart,
            simulate_gateway_error=simulate_error
        )

        if not payment_res.get("success", False):
            # Error classification: user error vs gateway error
            err_type = payment_res.get("error_type", "gateway_error")
            err_msg = payment_res.get("error_message", "Transaction failed.")
            return {
                "last_agent": "checkout",
                "hitl_pending": False,
                "payment_status": "failed",
                "error_context": {
                    "error_type": err_type,
                    "message": err_msg,
                    "retry_confirmed": False
                },
                "agent_output": {
                    "action": "payment_failed",
                    "error_type": err_type,
                    "error_message": err_msg
                },
                "response_message": (
                    f"⚠️ **Payment Error Encountered** [{err_type.upper()}]:\n"
                    f"{err_msg}\n\n"
                    f"*Policy: We never retry payments automatically without your explicit consent.* "
                    f"Would you like to retry the payment now? Reply 'Yes' to confirm retry or 'No' to cancel."
                )
            }

        # Payment link generated successfully
        order_id = payment_res.get("order_id")
        payment_url = payment_res.get("payment_url")
        return {
            "last_agent": "checkout",
            "hitl_pending": False,
            "payment_status": "link_created",
            "payment_details": payment_res,
            "agent_output": {
                "action": "payment_link_created",
                "order_id": order_id,
                "amount": totals["total"],
                "payment_url": payment_url
            },
            "response_message": (
                f"🎉 **Razorpay Payment Link Ready!**\n\n"
                f"• **Order ID:** `{order_id}`\n"
                f"• **Items:** {items_summary}\n"
                f"• **Total Amount:** ₹{totals['total']:,.2f} (incl. 18% GST)\n\n"
                f"🔗 **[Click here to complete payment on Razorpay]({payment_url})**\n\n"
                f"Once paid, your order will be instantly confirmed."
            )
        }

    # 4. Initial Checkout Stage: Surface HITL Approval Notice
    hitl_notice = (
        f"🛒 **Checkout Summary & Approval Required**\n\n"
        f"• **Items:** {items_summary}\n"
        f"• **Subtotal:** ₹{totals['subtotal']:,.2f}\n"
        f"• **GST (18%):** ₹{totals['tax']:,.2f}\n"
        f"• **Final Total:** **₹{totals['total']:,.2f}**\n\n"
        f"⚠️ **Human-in-the-Loop Confirmation:**\n"
        f"You are about to initiate a payment of **₹{totals['total']:,.2f}** via Razorpay. "
        f"Please reply **'Yes'** or click **Confirm Payment** to generate your secure payment link."
    )

    return {
        "last_agent": "checkout",
        "hitl_pending": True,
        "payment_status": "pending_approval",
        "agent_output": {
            "action": "hitl_approval_requested",
            "cart_totals": totals,
            "items": cart
        },
        "response_message": hitl_notice
    }
