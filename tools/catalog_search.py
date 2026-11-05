"""Catalog Search Tool for Buyer Agent."""
import re
from typing import List, Dict, Any, Optional
from tools.db import get_all_products, get_product_by_id

CONFIDENCE_THRESHOLD = 0.30

def tokenize(text: str) -> set:
    """Extract clean lowercase alphanumeric tokens."""
    return set(re.findall(r'\b[a-z0-9]+\b', text.lower()))

def search_catalog(
    query: str,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Search SQLite product catalog and rank results.
    Returns up to `limit` items with calculated match confidence.
    If no relevant match exceeds the threshold, returns empty list to prevent hallucinations.
    """
    products = get_all_products()
    query_tokens = tokenize(query)
    
    # Common stop words to ignore
    stop_words = {"i", "want", "to", "buy", "looking", "for", "a", "an", "the", "show", "me", "find", "some", "best", "good", "need", "get"}
    filtered_tokens = query_tokens - stop_words
    if not filtered_tokens:
        filtered_tokens = query_tokens

    scored_products = []

    for p in products:
        # Check category filter
        if category and p["category"].lower() != category.lower():
            continue
        
        # Check price filter
        if max_price is not None and p["price"] > max_price:
            continue

        name_tokens = tokenize(p["name"])
        category_tokens = tokenize(p["category"])
        desc_tokens = tokenize(p["description"])
        all_tokens = name_tokens | category_tokens | desc_tokens

        # Scoring weights
        name_matches = len(filtered_tokens & name_tokens)
        cat_matches = len(filtered_tokens & category_tokens)
        desc_matches = len(filtered_tokens & desc_tokens)

        # Exact substring matches in name or description boost
        query_lower = query.lower().strip()
        exact_boost = 0.0
        if p["name"].lower() in query_lower or query_lower in p["name"].lower():
            exact_boost += 0.5
        elif p["category"].lower() in query_lower:
            exact_boost += 0.3

        if not filtered_tokens:
            score = 0.0
        else:
            token_score = (name_matches * 3.0 + cat_matches * 2.0 + desc_matches * 1.0) / (len(filtered_tokens) * 3.0)
            score = min(1.0, token_score + exact_boost)

        if score >= CONFIDENCE_THRESHOLD:
            scored_products.append({
                "product": p,
                "confidence": round(score, 2)
            })

    # Sort descending by confidence, then by rating
    scored_products.sort(key=lambda x: (x["confidence"], x["product"]["rating"]), reverse=True)
    return scored_products[:limit]

def get_product_details(product_id: str) -> Optional[Dict[str, Any]]:
    return get_product_by_id(product_id)
