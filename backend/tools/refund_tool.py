
import json
from uuid import UUID
from decimal import Decimal, InvalidOperation

import httpx
from langchain_core.tools import tool


@tool
def get_refund_details(refund_id: str) -> str:
    """
    Retrieve the details and current status of an
    existing customer refund request.

    Use when a customer asks about:
    - Refund status
    - Refund approval or rejection
    - Refund amount or reason

    Requires a refund UUID, not an order UUID.
    """

    print(f"REFUND TOOL STARTED: {refund_id}", flush=True)

    # 1. Validate refund UUID
    try:
        refund_id = str(UUID(refund_id))
    except (ValueError, TypeError):
        return "Invalid refund ID."

    # 2. Call existing FastAPI endpoint
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/refunds/{refund_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            return "No refund request was found with that ID."

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve refund information right now."

    refund = response.json()

    print(f"REFUND TOOL CALLED: {refund_id}", flush=True)

    return json.dumps(refund)


@tool
def prepare_refund_request(
    customer_id: str,
    order_id: str,
    reason: str,
    amount: str | float | None = None,
    full_refund: bool = False
) -> str:
    """
    Prepare a customer refund request for confirmation.

    Use when a customer wants to request a refund.

    Required:
    - customer_id: Customer UUID
    - order_id: Order UUID
    - reason: Reason for the refund

    Optional:
    - amount: Customer-specified partial refund amount
    - full_refund: True only when the customer
      explicitly requests a full refund.

    If full_refund is True, retrieve the actual
    order total from the database automatically.

    If neither full_refund nor amount is specified,
    ask whether the customer wants a full or
    partial refund.

    This tool ONLY prepares a draft.
    It does NOT submit the refund request.
    """

    print("REFUND DRAFT TOOL STARTED", flush=True)

    # 1. Validate customer UUID
    try:
        customer_id = str(UUID(customer_id))
    except (ValueError, TypeError):
        return "Invalid customer ID."

    # 2. Validate order UUID
    try:
        order_id = str(UUID(order_id))
    except (ValueError, TypeError):
        return "Invalid order ID."

    # 3. Validate reason
    reason = reason.strip()

    if not reason:
        return "Please provide a reason for the refund."

    # 4. Retrieve order details from our existing API
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/orders/{order_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            return "Order not found."

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve the order details."

    order = response.json()

    # 5. Verify customer owns the order
    if str(order["customer_id"]) != customer_id:
        return "This order does not belong to the customer."

    # 6. Check our store's refund eligibility rule
    if order["status"] not in ("shipped", "delivered"):
        return (
            "Refund requests are only available for "
            "shipped or delivered orders. "
            "Please consider an order cancellation instead."
        )

    order_total = Decimal(str(order["total_amount"]))

    # 7. Determine refund amount
    if full_refund:

        # Always use the real order total for full refunds
        amount = order_total

    elif amount is None:

        return (
            "Would you like a full refund or a "
            "partial refund? For a partial refund, "
            "please specify the amount."
        )

    # 8. Validate amount
    try:
        refund_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return "Invalid refund amount."

    if (
        not refund_amount.is_finite()
        or refund_amount <= 0
        or refund_amount > Decimal("99999999.99")
    ):
        return "Refund amount must be a valid positive amount."

    if refund_amount != refund_amount.quantize(
        Decimal("0.01")
    ):
        return "Refund amount can have at most 2 decimal places."

    if refund_amount > order_total:
        return "Refund amount cannot exceed the order total."

    # 9. Prepare the refund draft
    draft = {
        "customer_id": customer_id,
        "order_id": order_id,
        "amount": str(refund_amount),
        "reason": reason
    }

    print("REFUND DRAFT PREPARED", flush=True)

    # 10. Return draft for confirmation
    return json.dumps({
        "confirmation_required": True,
        "draft": draft
    })
