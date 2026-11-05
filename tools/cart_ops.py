"""Cart Operations Tool for Cart Management and Validation."""
from typing import List, Dict, Any, Tuple
from tools.db import get_product_by_id

def add_to_cart(cart: List[Dict[str, Any]], product_id: str, quantity: int = 1) -> Tuple[List[Dict[str, Any]], str]:
    """Add a product to the user's cart after checking stock availability."""
    product = get_product_by_id(product_id)
    if not product:
        return cart, f"Product '{product_id}' not found in catalog."
    
    if product["stock"] < quantity:
        return cart, f"Insufficient stock for {product['name']}. Available: {product['stock']}."

    updated_cart = [dict(item) for item in cart]
    found = False
    for item in updated_cart:
        if item["product_id"] == product_id:
            if product["stock"] < item["quantity"] + quantity:
                return cart, f"Cannot add {quantity} more; total exceeds available stock ({product['stock']})."
            item["quantity"] += quantity
            found = True
            break
            
    if not found:
        updated_cart.append({
            "product_id": product["id"],
            "name": product["name"],
            "price": float(product["price"]),
            "quantity": quantity,
            "category": product["category"]
        })

    return updated_cart, f"Added {quantity}x {product['name']} to cart."

def remove_from_cart(cart: List[Dict[str, Any]], product_id: str) -> Tuple[List[Dict[str, Any]], str]:
    """Remove a product from the user's cart."""
    updated_cart = [item for item in cart if item["product_id"] != product_id]
    if len(updated_cart) == len(cart):
        return cart, f"Item '{product_id}' not found in cart."
    return updated_cart, f"Removed item from cart."

def calculate_cart_totals(cart: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate subtotal, GST (18%), and final total amount."""
    subtotal = sum(item["price"] * item["quantity"] for item in cart)
    gst = round(subtotal * 0.18, 2)
    total = round(subtotal + gst, 2)
    return {
        "subtotal": round(subtotal, 2),
        "tax": gst,
        "total": total,
        "item_count": sum(item["quantity"] for item in cart)
    }

def validate_cart(cart: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Validate cart state before checkout."""
    if not cart or len(cart) == 0:
        return False, "Cart is empty. Please add items before proceeding to checkout."
    
    for item in cart:
        product = get_product_by_id(item["product_id"])
        if not product:
            return False, f"Product {item['name']} ({item['product_id']}) is no longer available."
        if product["stock"] < item["quantity"]:
            return False, f"Product {item['name']} exceeds available stock ({product['stock']})."
    
    return True, "Cart validated successfully."
