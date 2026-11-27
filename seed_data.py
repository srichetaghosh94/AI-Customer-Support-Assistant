"""Seed the AI Customer Support demo PostgreSQL database with fictional data.

Dependencies:
    py -m pip install "psycopg[binary]" faker

PowerShell example:
    $env:PGPASSWORD = "your_postgresql_password"
    $env:PGDATABASE = "ai_customer_support"
    py seed_data.py

This script only inserts into EMPTY tables and will not delete existing data.
The database schema must already exist (the 9 UUID-keyed tables).
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
from psycopg import sql
from faker import Faker


# Same output for the same script, except timestamps relative to run time and UUIDs.
random.seed(42)
Faker.seed(42)
fake = Faker("en_GB")
NOW = datetime.now(timezone.utc)
MONEY = Decimal("0.01")

TABLES = [
    "customers",
    "products",
    "orders",
    "order_items",
    "shipments",
    "admin_users",
    "support_tickets",
    "refund_requests",
    "cancellation_requests",
]


# (Product name, useful description, standard price in EUR)
BASE_PRODUCTS = [
    ("Wireless Earbuds", "Bluetooth earbuds with charging case and built-in microphone", "39.90"),
    ("Bluetooth Speaker", "Portable speaker with rechargeable battery", "49.90"),
    ("Mechanical Keyboard", "USB keyboard with mechanical switches", "69.90"),
    ("Wireless Mouse", "Ergonomic wireless mouse with adjustable sensitivity", "24.90"),
    ("USB-C Charger", "Fast USB-C wall charger for phones and tablets", "19.90"),
    ("Laptop Stand", "Adjustable metal stand for laptops", "29.90"),
    ("1080p Webcam", "Full-HD webcam with built-in microphone", "54.90"),
    ("Power Bank", "Portable USB-C battery pack", "34.90"),
    ("Smart Watch", "Fitness tracking watch with notification support", "89.90"),
    ("Portable SSD", "USB-C external solid-state storage drive", "79.90"),
]
VARIANTS = [
    ("Lite", Decimal("0.80")),
    ("Standard", Decimal("1.00")),
    ("Plus", Decimal("1.20")),
    ("Pro", Decimal("1.50")),
    ("Max", Decimal("1.80")),
]


def connect() -> psycopg.Connection:
    """Use DATABASE_URL or standard PostgreSQL environment variables."""
    url = os.getenv("DATABASE_URL")
    if url:
        return psycopg.connect(url)
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ai_customer_support"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD"),
    )


def require_empty_tables(cur: psycopg.Cursor) -> None:
    """Prevent accidentally adding duplicate seed data to a populated database."""
    for table in TABLES:
        query = sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(
            sql.Identifier(table)
        )
        cur.execute(query)
        if cur.fetchone()[0]:
            raise RuntimeError(
                f"Table '{table}' already contains data. "
                "Seed a new empty database; this script never clears tables."
            )


def seed_admins(cur: psycopg.Cursor) -> list:
    admins = []
    for i, name in enumerate(["Alex Morgan", "Jordan Lee", "Taylor Parker"], 1):
        cur.execute(
            """INSERT INTO admin_users (full_name, email)
               VALUES (%s, %s) RETURNING admin_id""",
            (name, f"admin{i}@example.com"),
        )
        admins.append(cur.fetchone()[0])
    return admins


def seed_customers(cur: psycopg.Cursor) -> list:
    customers = []
    for i in range(1, 31):
        # example.com is reserved for sample data: no real customer addresses.
        name = fake.name()
        email = f"customer{i:03d}@example.com"
        cur.execute(
            """INSERT INTO customers (full_name, email)
               VALUES (%s, %s) RETURNING customer_id""",
            (name, email),
        )
        customers.append(cur.fetchone()[0])
    return customers


def seed_products(cur: psycopg.Cursor) -> list[dict]:
    products = []
    for base_name, base_desc, base_price in BASE_PRODUCTS:
        for variant_name, multiplier in VARIANTS:
            price = (Decimal(base_price) * multiplier).quantize(MONEY)
            cur.execute(
                """INSERT INTO products
                       (name, description, price, stock_quantity, is_active)
                   VALUES (%s, %s, %s, %s, TRUE)
                   RETURNING product_id""",
                (
                    f"{base_name} {variant_name}",
                    f"{base_desc}. {variant_name} edition.",
                    price,
                    random.randint(20, 120),
                ),
            )
            products.append({"id": cur.fetchone()[0], "price": price})
    return products


def order_created_at(status: str) -> datetime:
    # The statuses and dates are kept broadly consistent for a realistic demo.
    days_old = {
        "pending": (0, 3),
        "processing": (1, 7),
        "shipped": (3, 15),
        "delivered": (15, 150),
        "cancelled": (5, 90),
    }
    low, high = days_old[status]
    return NOW - timedelta(days=random.randint(low, high), hours=random.randint(0, 23))


def seed_orders(cur: psycopg.Cursor, customers: list, products: list[dict]) -> list[dict]:
    statuses = (
        ["pending"] * 12
        + ["processing"] * 15
        + ["shipped"] * 38
        + ["delivered"] * 70
        + ["cancelled"] * 15
    )
    random.shuffle(statuses)
    # Every customer gets five orders, for more useful chatbot demos.
    buyer_ids = customers * 5
    random.shuffle(buyer_ids)
    orders = []

    for status, customer_id in zip(statuses, buyer_ids):
        item_count = random.choices([1, 2, 3], weights=[35, 50, 15])[0]
        chosen = random.sample(products, k=item_count)
        items = []
        for product in chosen:
            quantity = random.randint(1, 3)
            items.append((product["id"], quantity, product["price"]))
        total_amount = sum((qty * price for _, qty, price in items), Decimal("0"))
        created_at = order_created_at(status)

        cur.execute(
            """INSERT INTO orders (customer_id, status, total_amount, created_at)
               VALUES (%s, %s, %s, %s) RETURNING order_id""",
            (customer_id, status, total_amount, created_at),
        )
        order_id = cur.fetchone()[0]
        for product_id, quantity, unit_price in items:
            cur.execute(
                """INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                   VALUES (%s, %s, %s, %s)""",
                (order_id, product_id, quantity, unit_price),
            )
        orders.append(
            {
                "id": order_id,
                "customer_id": customer_id,
                "status": status,
                "total": total_amount,
                "created_at": created_at,
            }
        )
    return orders


def seed_shipments(cur: psycopg.Cursor, orders: list[dict]) -> None:
    delivered = random.sample([o for o in orders if o["status"] == "delivered"], 65)
    shipped = random.sample([o for o in orders if o["status"] == "shipped"], 35)
    selected = delivered + shipped
    random.shuffle(selected)

    for i, order in enumerate(selected, 1):
        was_delivered = order["status"] == "delivered"
        shipment_status = (
            "delivered" if was_delivered
            else random.choices(["in_transit", "exception"], weights=[85, 15])[0]
        )
        delivery_date = (order["created_at"] + timedelta(days=7)).date()
        delivered_at = (
            order["created_at"] + timedelta(days=random.randint(2, 6))
            if was_delivered else None
        )
        cur.execute(
            """INSERT INTO shipments
                   (order_id, carrier, tracking_number, status,
                    estimated_delivery, delivered_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                order["id"],
                random.choice(["DHL", "DPD", "GLS", "UPS"]),
                f"DEMO-TRACK-{i:06d}",
                shipment_status,
                delivery_date,
                delivered_at,
            ),
        )


def seed_tickets(cur: psycopg.Cursor, orders: list[dict]) -> None:
    templates = {
        "pending": ("Order confirmation question", "I placed an order. When will it be processed?"),
        "processing": ("Change delivery details", "Can I update the delivery details for my order?"),
        "shipped": ("Delivery delay", "My order has shipped but I have not received it yet."),
        "delivered": ("Product issue", "The item arrived, but I need help with a product issue."),
        "cancelled": ("Cancellation question", "Can you confirm that my order was cancelled?"),
    }
    for order in random.sample(orders, 40):
        subject, description = templates[order["status"]]
        created_at = min(
            NOW,
            order["created_at"] + timedelta(days=random.randint(0, 6)),
        )
        cur.execute(
            """INSERT INTO support_tickets
                   (customer_id, order_id, subject, description, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                order["customer_id"], order["id"], subject, description,
                random.choices(
                    ["open", "in_progress", "resolved", "closed"],
                    weights=[35, 30, 25, 10],
                )[0],
                created_at,
            ),
        )


def seed_refunds(cur: psycopg.Cursor, orders: list[dict], admins: list) -> None:
    eligible = random.sample([o for o in orders if o["status"] == "delivered"], 20)
    statuses = ["pending"] * 7 + ["approved"] * 8 + ["rejected"] * 5
    random.shuffle(statuses)
    for order, status in zip(eligible, statuses):
        amount = (order["total"] * random.choice([Decimal("0.50"), Decimal("1.00")])).quantize(MONEY)
        created_at = order["created_at"] + timedelta(days=random.randint(7, 12))
        reviewed_by = random.choice(admins) if status != "pending" else None
        reviewed_at = (
            created_at + timedelta(days=random.randint(1, 2))
            if reviewed_by is not None else None
        )
        cur.execute(
            """INSERT INTO refund_requests
                   (order_id, amount, reason, status, reviewed_by, reviewed_at, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                order["id"], amount,
                random.choice(["Damaged item", "Item not as described", "Wrong item received"]),
                status, reviewed_by, reviewed_at, created_at,
            ),
        )


def seed_cancellations(cur: psycopg.Cursor, orders: list[dict], admins: list) -> None:
    # Approved requests correspond to cancelled orders; other requests are
    # still pending or were rejected, so the order itself is not cancelled.
    selected = (
        [(o, "approved") for o in random.sample([o for o in orders if o["status"] == "cancelled"], 6)]
        + [(o, "pending") for o in random.sample([o for o in orders if o["status"] == "pending"], 5)]
        + [(o, "rejected") for o in random.sample([o for o in orders if o["status"] == "processing"], 4)]
    )
    random.shuffle(selected)
    for order, status in selected:
        created_at = min(NOW, order["created_at"] + timedelta(hours=5))
        reviewed_by = random.choice(admins) if status != "pending" else None
        reviewed_at = (
            min(NOW, created_at + timedelta(hours=2)) if reviewed_by else None
        )
        cur.execute(
            """INSERT INTO cancellation_requests
                   (order_id, reason, status, reviewed_by, reviewed_at, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                order["id"],
                random.choice(["Ordered by mistake", "Changed my mind", "Delivery would take too long"]),
                status, reviewed_by, reviewed_at, created_at,
            ),
        )


def main() -> None:
    with connect() as conn:
        # A single transaction: PostgreSQL rolls everything back if any insert fails.
        with conn.cursor() as cur:
            require_empty_tables(cur)
            admins = seed_admins(cur)
            customers = seed_customers(cur)
            products = seed_products(cur)
            orders = seed_orders(cur, customers, products)
            seed_shipments(cur, orders)
            seed_tickets(cur, orders)
            seed_refunds(cur, orders, admins)
            seed_cancellations(cur, orders, admins)

            print("\nSeeded fictional e-commerce data successfully:")
            for table in TABLES:
                query = sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                cur.execute(query)
                print(f"  {table:24s} {cur.fetchone()[0]:>4}")

            cur.execute(
                """SELECT c.email, o.order_id, o.status
                   FROM orders o JOIN customers c ON c.customer_id = o.customer_id
                   ORDER BY o.created_at DESC LIMIT 5"""
            )
            print("\nExample customer email / order ID / status for testing:")
            for email, order_id, status in cur.fetchall():
                print(f"  {email} | {order_id} | {status}")

    print("\nDone. All data is fictional; emails use example.com.")


if __name__ == "__main__":
    try:
        main()
    except (psycopg.Error, RuntimeError) as exc:
        raise SystemExit(f"Could not seed database: {exc}") from exc
