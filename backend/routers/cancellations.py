
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from database import engine
from typing import Literal

router = APIRouter(prefix="/cancellations", tags=["Cancellations"])


# Request body
class CancellationCreate(BaseModel):
    customer_id: UUID
    order_id: UUID
    reason: str | None = None


# Response body
class CancellationDetail(BaseModel):
    cancellation_id: UUID
    order_id: UUID
    reason: str | None
    status: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime | None

class CancellationReview(BaseModel):
    admin_name: str
    admin_email: str
    status: Literal["approved", "rejected"]


@router.post(
    "",
    response_model=CancellationDetail,
    status_code=status.HTTP_201_CREATED
)
def create_cancellation(request: CancellationCreate):

    with engine.begin() as conn:

        # 1. Check order ownership and lock the order
        order = conn.execute(
            text("""
                SELECT status
                FROM orders
                WHERE order_id = :order_id
                  AND customer_id = :customer_id
                FOR UPDATE
            """),
            {
                "order_id": request.order_id,
                "customer_id": request.customer_id
            }
        ).mappings().first()

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found for this customer"
            )

        # 2. Check cancellation eligibility
        if order["status"] not in ("pending", "processing"):
            raise HTTPException(
                status_code=400,
                detail="Order cannot be cancelled after shipping"
            )

        # 3. Prevent duplicate cancellation requests
        existing = conn.execute(
            text("""
                SELECT 1
                FROM cancellation_requests
                WHERE order_id = :order_id
            """),
            {"order_id": request.order_id}
        ).first()

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Cancellation request already exists"
            )

        # 4. Create cancellation request
        cancellation = conn.execute(
            text("""
                INSERT INTO cancellation_requests (
                    order_id,
                    reason
                )
                VALUES (:order_id, :reason)
                RETURNING *
            """),
            {
                "order_id": request.order_id,
                "reason": request.reason
            }
        ).mappings().one()

    return dict(cancellation)


@router.patch(
    "/{cancellation_id}",
    response_model=CancellationDetail
)
def review_cancellation(
    cancellation_id: UUID,
    review: CancellationReview
):

    with engine.begin() as conn:

        # 1. Check if admin exists
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

        # 2. Find and lock the cancellation request
        cancellation = conn.execute(
            text("""
                SELECT order_id, status
                FROM cancellation_requests
                WHERE cancellation_id = :cancellation_id
                FOR UPDATE
            """),
            {"cancellation_id": cancellation_id}
        ).mappings().first()

        if cancellation is None:
            raise HTTPException(
                status_code=404,
                detail="Cancellation request not found"
            )

        # 3. Only pending requests can be reviewed
        if cancellation["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail="Cancellation already reviewed"
            )

        # 4. If approved, cancel the order
        if review.status == "approved":

            updated_order = conn.execute(
                text("""
                    UPDATE orders
                    SET status = 'cancelled'
                    WHERE order_id = :order_id
                      AND status IN ('pending', 'processing')
                    RETURNING order_id
                """),
                {"order_id": cancellation["order_id"]}
            ).first()

            if updated_order is None:
                raise HTTPException(
                    status_code=409,
                    detail="Order is no longer eligible for cancellation"
                )

        # 5. Record admin's decision
        updated_cancellation = conn.execute(
            text("""
                UPDATE cancellation_requests
                SET
                    status = :status,
                    reviewed_by = :admin_id,
                    reviewed_at = NOW()
                WHERE cancellation_id = :cancellation_id
                RETURNING *
            """),
            {
                "status": review.status,
                "admin_id": admin["admin_id"],
                "cancellation_id": cancellation_id
            }
        ).mappings().one()

    return dict(updated_cancellation)


@router.get("/{cancellation_id}", response_model=CancellationDetail)
def get_cancellation(cancellation_id: UUID):

    with engine.connect() as conn:
        cancellation = conn.execute(
            text("""
                SELECT *
                FROM cancellation_requests
                WHERE cancellation_id = :cancellation_id
            """),
            {"cancellation_id": cancellation_id}
        ).mappings().first()

    if cancellation is None:
        raise HTTPException(
            status_code=404,
            detail="Cancellation request not found"
        )

    return dict(cancellation)


