
from decimal import Decimal
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from database import engine
from routers.tickets import TicketDetail

router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerDetail(BaseModel):
    customer_id: UUID
    full_name: str
    email: str
    created_at: datetime | None


class OrderProduct(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int


class CustomerOrder(BaseModel):
    order_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime | None
    items: list[OrderProduct]



@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: UUID):

    with engine.connect() as conn:
        customer = conn.execute(
            text("""
                SELECT *
                FROM customers
                WHERE customer_id = :customer_id
            """),
            {"customer_id": customer_id}
        ).mappings().first()

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    return dict(customer)




@router.get("/{customer_id}/orders", response_model=list[CustomerOrder])
def get_customer_orders(customer_id: UUID):

    with engine.connect() as conn:

        # Check whether the customer exists
        customer_exists = conn.execute(
            text("""
                SELECT 1
                FROM customers
                WHERE customer_id = :customer_id
            """),
            {"customer_id": customer_id}
        ).first()

        if customer_exists is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        # Retrieve orders with their purchased products
        rows = conn.execute(
            text("""
                SELECT
                    o.order_id,
                    o.status,
                    o.total_amount,
                    o.created_at,
                    p.product_id,
                    p.name AS product_name,
                    oi.quantity
                FROM orders o
                LEFT JOIN order_items oi
                    ON o.order_id = oi.order_id
                LEFT JOIN products p
                    ON oi.product_id = p.product_id
                WHERE o.customer_id = :customer_id
                ORDER BY o.created_at DESC, p.name
            """),
            {"customer_id": customer_id}
        ).mappings().all()

    # Group products under their corresponding orders
    orders = {}

    for row in rows:
        order_id = row["order_id"]

        if order_id not in orders:
            orders[order_id] = {
                "order_id": order_id,
                "status": row["status"],
                "total_amount": row["total_amount"],
                "created_at": row["created_at"],
                "items": []
            }

        if row["product_id"] is not None:
            orders[order_id]["items"].append({
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "quantity": row["quantity"]
            })

    return list(orders.values())


@router.get("/{customer_id}/tickets", response_model=list[TicketDetail])
def get_customer_tickets(customer_id: UUID):

    with engine.connect() as conn:

        # Check whether the customer exists
        customer_exists = conn.execute(
            text("""
                SELECT 1 FROM customers
                WHERE customer_id = :customer_id
            """),
            {"customer_id": customer_id}
        ).first()

        if customer_exists is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        # Retrieve all tickets belonging to the customer
        tickets = conn.execute(
            text("""
                SELECT
                    ticket_id,
                    customer_id,
                    order_id,
                    subject,
                    description,
                    status,
                    created_at
                FROM support_tickets
                WHERE customer_id = :customer_id
                ORDER BY created_at DESC
            """),
            {"customer_id": customer_id}
        ).mappings().all()

    return [dict(ticket) for ticket in tickets]
