from uuid import UUID
from decimal import Decimal
from datetime import datetime, date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from database import engine

router = APIRouter(prefix="/orders", tags=["Orders"])


class OrderItem(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderDetail(BaseModel):
    order_id: UUID
    customer_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime | None
    items: list[OrderItem]


class ShipmentDetail(BaseModel):
    shipment_id: UUID
    order_id: UUID
    carrier: str | None
    tracking_number: str | None
    status: str
    estimated_delivery: date | None
    delivered_at: datetime | None



@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: UUID):

    with engine.connect() as conn:
        order = conn.execute(
            text("""
                SELECT order_id, customer_id, status,
                       total_amount, created_at
                FROM orders
                WHERE order_id = :order_id
            """),
            {"order_id": order_id}
        ).mappings().first()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        items = conn.execute(
            text("""
                SELECT
                    oi.product_id,
                    p.name AS product_name,
                    oi.quantity,
                    oi.unit_price,
                    oi.quantity * oi.unit_price AS subtotal
                FROM order_items oi
                JOIN products p
                    ON oi.product_id = p.product_id
                WHERE oi.order_id = :order_id
            """),
            {"order_id": order_id}
        ).mappings().all()

    return {
        **dict(order),
        "items": [dict(item) for item in items]
    }


@router.get("/{order_id}/shipment", response_model=ShipmentDetail)
def get_order_shipment(order_id: UUID):

    with engine.connect() as conn:
        shipment = conn.execute(
            text("""
                SELECT
                    shipment_id,
                    order_id,
                    carrier,
                    tracking_number,
                    status,
                    estimated_delivery,
                    delivered_at
                FROM shipments
                WHERE order_id = :order_id
            """),
            {"order_id": order_id}
        ).mappings().first()

    if shipment is None:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found for this order"
        )

    return dict(shipment)
