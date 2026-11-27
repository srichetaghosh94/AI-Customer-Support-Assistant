
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import engine
from typing import Literal

router = APIRouter(prefix="/refunds", tags=["Refunds"])


# Request body
class RefundCreate(BaseModel):
    customer_id: UUID
    order_id: UUID
    amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2
    )
    reason: str = Field(min_length=1)


# Response body
class RefundDetail(BaseModel):
    refund_id: UUID
    order_id: UUID
    amount: Decimal
    reason: str
    status: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime | None


class RefundReview(BaseModel):
    admin_name: str
    admin_email: str
    status: Literal["approved", "rejected"]



@router.post(
    "",
    response_model=RefundDetail,
    status_code=status.HTTP_201_CREATED
)
def create_refund(refund: RefundCreate):

    with engine.begin() as conn:

        # 1. Check that the order belongs to the customer
        order = conn.execute(
            text("""
                SELECT order_id, total_amount, status
                FROM orders
                WHERE order_id = :order_id
                  AND customer_id = :customer_id
            """),
            {
                "order_id": refund.order_id,
                "customer_id": refund.customer_id
            }
        ).mappings().first()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found for this customer"
            )

        # 2. Validate refund amount
        if refund.amount > order["total_amount"]:
            raise HTTPException(
                status_code=400,
                detail="Refund amount exceeds order total"
            )

        # 3. Prevent another pending refund for the order
        existing = conn.execute(
            text("""
                SELECT 1
                FROM refund_requests
                WHERE order_id = :order_id
                  AND status = 'pending'
            """),
            {"order_id": refund.order_id}
        ).first()

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="A pending refund already exists for this order"
            )

        # 4. Insert refund request
        new_refund = conn.execute(
            text("""
                INSERT INTO refund_requests (
                    order_id,
                    amount,
                    reason
                )
                VALUES (
                    :order_id,
                    :amount,
                    :reason
                )
                RETURNING
                    refund_id,
                    order_id,
                    amount,
                    reason,
                    status,
                    reviewed_by,
                    reviewed_at,
                    created_at
            """),
            {
                "order_id": refund.order_id,
                "amount": refund.amount,
                "reason": refund.reason
            }
        ).mappings().one()

    return dict(new_refund)

@router.get("/{refund_id}", response_model=RefundDetail)
def get_refund(refund_id: UUID):

    with engine.connect() as conn:
        refund = conn.execute(
            text("""
                SELECT *
                FROM refund_requests
                WHERE refund_id = :refund_id
            """),
            {"refund_id": refund_id}
        ).mappings().first()

    if refund is None:
        raise HTTPException(
            status_code=404,
            detail="Refund request not found"
        )

    return dict(refund)


@router.patch("/{refund_id}", response_model=RefundDetail)
def review_refund(refund_id: UUID, review: RefundReview):

    with engine.begin() as conn:

        # 1. Check whether the admin exists
        admin = conn.execute(
            text("""
                SELECT admin_id
                FROM admin_users
                WHERE full_name = :admin_name
                  AND email = :admin_email
            """),
            {
                "admin_name": review.admin_name,
                "admin_email": review.admin_email
            }
        ).mappings().first()

        if admin is None:
            raise HTTPException(
                status_code=403,
                detail="Admin not recognized"
            )

        # 2. Check refund exists and lock it during review
        refund = conn.execute(
            text("""
                SELECT status
                FROM refund_requests
                WHERE refund_id = :refund_id
                FOR UPDATE
            """),
            {"refund_id": refund_id}
        ).mappings().first()

        if refund is None:
            raise HTTPException(
                status_code=404,
                detail="Refund request not found"
            )

        # 3. Only pending refunds can be reviewed
        if refund["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="Refund has already been reviewed"
            )

        # 4. Update the refund request
        updated_refund = conn.execute(
            text("""
                UPDATE refund_requests
                SET
                    status = :status,
                    reviewed_by = :admin_id,
                    reviewed_at = NOW()
                WHERE refund_id = :refund_id
                RETURNING *
            """),
            {
                "status": review.status,
                "admin_id": admin["admin_id"],
                "refund_id": refund_id
            }
        ).mappings().one()

    return dict(updated_refund)
