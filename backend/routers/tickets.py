
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import engine

router = APIRouter(prefix="/tickets", tags=["Support Tickets"])


# Request body: Data required to create a ticket
class TicketCreate(BaseModel):
    customer_id: UUID
    order_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)


# Response body: Data returned after creation
class TicketDetail(BaseModel):
    ticket_id: UUID
    customer_id: UUID
    order_id: UUID | None
    subject: str
    description: str
    status: str
    created_at: datetime | None


@router.post(
    "",
    response_model=TicketDetail,
    status_code=status.HTTP_201_CREATED
)
def create_ticket(ticket: TicketCreate):

    with engine.begin() as conn:

        # 1. Check if customer exists
        customer = conn.execute(
            text("""
                SELECT 1
                FROM customers
                WHERE customer_id = :customer_id
            """),
            {"customer_id": ticket.customer_id}
        ).first()

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        # 2. If an order was provided, check that it
        # belongs to this customer
        if ticket.order_id is not None:
            order = conn.execute(
                text("""
                    SELECT 1
                    FROM orders
                    WHERE order_id = :order_id
                      AND customer_id = :customer_id
                """),
                {
                    "order_id": ticket.order_id,
                    "customer_id": ticket.customer_id
                }
            ).first()

            if order is None:
                raise HTTPException(
                    status_code=404,
                    detail="Order not found for this customer"
                )

        # 3. Insert support ticket into PostgreSQL
        new_ticket = conn.execute(
            text("""
                INSERT INTO support_tickets (
                    customer_id,
                    order_id,
                    subject,
                    description
                )
                VALUES (
                    :customer_id,
                    :order_id,
                    :subject,
                    :description
                )
                RETURNING
                    ticket_id,
                    customer_id,
                    order_id,
                    subject,
                    description,
                    status,
                    created_at
            """),
            {
                "customer_id": ticket.customer_id,
                "order_id": ticket.order_id,
                "subject": ticket.subject,
                "description": ticket.description
            }
        ).mappings().one()

    return dict(new_ticket)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: UUID):

    with engine.connect() as conn:
        ticket = conn.execute(
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
                WHERE ticket_id = :ticket_id
            """),
            {"ticket_id": ticket_id}
        ).mappings().first()

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Support ticket not found"
        )

    return dict(ticket)

