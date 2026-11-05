"""SQLite Database Layer for Product Catalog and Order History."""
import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "commerce.db")

SAMPLE_PRODUCTS = [
    {
        "id": "prod_phone_15",
        "name": "Apex Phone 15 Pro",
        "category": "Smartphones",
        "description": "Flagship 6.7-inch OLED smartphone with titanium chassis, 120Hz display, and A17 Bionic chip.",
        "price": 119999.00,
        "stock": 25,
        "rating": 4.8,
        "complementary_ids": json.dumps(["prod_charger_65w", "prod_case_15"])
    },
    {
        "id": "prod_phone_lite",
        "name": "Apex Phone Lite",
        "category": "Smartphones",
        "description": "Affordable 6.4-inch smartphone with 5G connectivity, 50MP camera, and 5000mAh battery.",
        "price": 24999.00,
        "stock": 50,
        "rating": 4.5,
        "complementary_ids": json.dumps(["prod_charger_65w", "prod_earbuds_pro"])
    },
    {
        "id": "prod_headphone_anc",
        "name": "AcousticMax Pro Wireless Headphones",
        "category": "Audio",
        "description": "Premium over-ear noise-cancelling headphones with 40-hour battery life and Hi-Res spatial audio.",
        "price": 18999.00,
        "stock": 35,
        "rating": 4.7,
        "complementary_ids": json.dumps(["prod_headphone_stand", "prod_audio_cable"])
    },
    {
        "id": "prod_earbuds_pro",
        "name": "PulseBuds Pro TWS",
        "category": "Audio",
        "description": "True wireless stereo earbuds with active noise cancellation, transparency mode, and IPX5 water resistance.",
        "price": 6999.00,
        "stock": 60,
        "rating": 4.6,
        "complementary_ids": json.dumps(["prod_charger_65w"])
    },
    {
        "id": "prod_laptop_ultra",
        "name": "ZenBook Ultra 14 Laptop",
        "category": "Laptops",
        "description": "Ultra-slim 14-inch laptop with Intel Core Ultra 7, 32GB RAM, 1TB SSD, and 2.8K OLED screen.",
        "price": 104999.00,
        "stock": 15,
        "rating": 4.9,
        "complementary_ids": json.dumps(["prod_laptop_sleeve", "prod_mouse_ergo", "prod_dock_hub"])
    },
    {
        "id": "prod_watch_ultra",
        "name": "Chronos Smartwatch Elite",
        "category": "Wearables",
        "description": "Rugged GPS smartwatch with sapphire crystal glass, 100m water resistance, and ECG cardiac monitoring.",
        "price": 28999.00,
        "stock": 40,
        "rating": 4.6,
        "complementary_ids": json.dumps(["prod_watch_strap"])
    },
    {
        "id": "prod_keyboard_mech",
        "name": "KeyCraft RGB Mechanical Keyboard",
        "category": "Accessories",
        "description": "Hot-swappable mechanical keyboard with custom linear switches, PBT keycaps, and per-key RGB lighting.",
        "price": 7499.00,
        "stock": 30,
        "rating": 4.7,
        "complementary_ids": json.dumps(["prod_mouse_ergo"])
    },
    {
        "id": "prod_mouse_ergo",
        "name": "SwiftGlide Ergonomic Wireless Mouse",
        "category": "Accessories",
        "description": "Ergonomic vertical wireless mouse designed to reduce wrist strain, featuring dual Bluetooth & 2.4G.",
        "price": 3499.00,
        "stock": 45,
        "rating": 4.4,
        "complementary_ids": json.dumps(["prod_keyboard_mech"])
    },
    {
        "id": "prod_charger_65w",
        "name": "HyperVolt 65W GaN Fast Charger",
        "category": "Accessories",
        "description": "Ultra-compact 65W GaN fast wall charger with dual USB-C and USB-A ports, compatible with laptops and phones.",
        "price": 2199.00,
        "stock": 80,
        "rating": 4.8,
        "complementary_ids": json.dumps([])
    },
    {
        "id": "prod_case_15",
        "name": "MagShield Magnetic Armor Case",
        "category": "Accessories",
        "description": "Military-grade drop protection case with integrated MagSafe magnets and tactile metal buttons.",
        "price": 1499.00,
        "stock": 70,
        "rating": 4.5,
        "complementary_ids": json.dumps(["prod_charger_65w"])
    },
    {
        "id": "prod_laptop_sleeve",
        "name": "UrbanLeather 14-inch Laptop Sleeve",
        "category": "Accessories",
        "description": "Water-resistant vegan leather laptop sleeve with fleece lining and magnetic closure.",
        "price": 1899.00,
        "stock": 50,
        "rating": 4.6,
        "complementary_ids": json.dumps(["prod_mouse_ergo"])
    },
    {
        "id": "prod_dock_hub",
        "name": "MultiConnect 8-in-1 USB-C Hub Dock",
        "category": "Accessories",
        "description": "Aluminum 8-in-1 USB-C hub with 4K HDMI, 100W Power Delivery, SD reader, and Gigabit Ethernet.",
        "price": 4299.00,
        "stock": 35,
        "rating": 4.7,
        "complementary_ids": json.dumps([])
    },
    {
        "id": "prod_headphone_stand",
        "name": "AuraGlow Aluminum Headphone Stand",
        "category": "Accessories",
        "description": "Heavy-base anodized aluminum headphone stand with silicone cradle and integrated cable organizer.",
        "price": 1299.00,
        "stock": 40,
        "rating": 4.3,
        "complementary_ids": json.dumps([])
    },
    {
        "id": "prod_audio_cable",
        "name": "Braided Hi-Fi 3.5mm Gold Audio Cable",
        "category": "Accessories",
        "description": "Oxygen-free copper braided 3.5mm audio cable with 24k gold-plated connectors for lossless audio.",
        "price": 799.00,
        "stock": 60,
        "rating": 4.5,
        "complementary_ids": json.dumps([])
    },
    {
        "id": "prod_watch_strap",
        "name": "Milanese Magnetic Loop Watch Strap",
        "category": "Wearables",
        "description": "Stainless steel breathable woven mesh strap with infinitely adjustable magnetic closure.",
        "price": 1299.00,
        "stock": 55,
        "rating": 4.5,
        "complementary_ids": json.dumps([])
    }
]

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            rating REAL NOT NULL,
            complementary_ids TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            items TEXT NOT NULL,
            total_amount REAL NOT NULL,
            payment_id TEXT,
            payment_link TEXT,
            payment_status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed products if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    if count == 0:
        for p in SAMPLE_PRODUCTS:
            cursor.execute("""
                INSERT INTO products (id, name, category, description, price, stock, rating, complementary_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["id"], p["name"], p["category"], p["description"], p["price"], p["stock"], p["rating"], p["complementary_ids"]))
        conn.commit()

    conn.close()

def get_all_products(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        item["complementary_ids"] = json.loads(item["complementary_ids"])
        results.append(item)
    return results

def get_product_by_id(product_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        item = dict(row)
        item["complementary_ids"] = json.loads(item["complementary_ids"])
        return item
    return None

def create_order_db(order_id: str, user_id: str, items: List[Dict[str, Any]], total_amount: float, payment_link: str, db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (order_id, user_id, items, total_amount, payment_link, payment_status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, user_id, json.dumps(items), total_amount, payment_link, "link_created"))
    conn.commit()
    conn.close()

def update_order_status_db(order_id: str, status: str, payment_id: Optional[str] = None, db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders SET payment_status = ?, payment_id = ? WHERE order_id = ?
    """, (status, payment_id, order_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with", len(SAMPLE_PRODUCTS), "products.")
