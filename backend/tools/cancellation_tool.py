
import json
from uuid import UUID

import httpx
from langchain_core.tools import tool


@tool
def get_cancellation_details(cancellation_id: str) -> str:
    """
    Retrieve the details and current status of an
    existing order cancellation request.

    Use when a customer asks about:
    - Cancellation request status
    - Whether their cancellation was approved
    - Whether their cancellation was rejected
    - An existing cancellation request

    Requires a cancellation UUID, not an order UUID.

    This tool only retrieves information.
    It does not submit or approve cancellations.
    """

    print(
        f"CANCELLATION TOOL STARTED: {cancellation_id}",
        flush=True
    )

    # 1. Validate cancellation UUID
    try:
        cancellation_id = str(UUID(cancellation_id))
    except (ValueError, TypeError):
        return "Invalid cancellation ID."

    # 2. Call our existing FastAPI endpoint
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/cancellations/{cancellation_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            return "No cancellation request was found with that ID."

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve cancellation information right now."

    # 3. Retrieve cancellation details
    cancellation = response.json()

    print(
        f"CANCELLATION TOOL CALLED: {cancellation_id}",
        flush=True
    )

    return json.dumps(cancellation)



@tool
def prepare_cancellation_request(
    customer_id: str,
    order_id: str,
    reason: str | None = None
) -> str:
    """
    Prepare an order cancellation request for confirmation.

    Use when a customer wants to cancel an existing order.

    Required:
    - customer_id: Customer UUID
    - order_id: Order UUID

    Optional:
    - reason: Reason for cancellation

    The order must be pending or processing.

    This tool prepares a draft only.
    It does NOT submit a cancellation request.
    """

    print("CANCELLATION DRAFT TOOL STARTED", flush=True)

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

    # 3. Validate optional reason
    if reason is not None:
        reason = reason.strip() or None

    # 4. Retrieve order details
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/orders/{order_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            return "Order not found."

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve order details."

    order = response.json()

    # 5. Verify order ownership
    if str(order["customer_id"]) != customer_id:
        return "This order does not belong to the customer."

    # 6. Check cancellation eligibility
    if order["status"] not in ("pending", "processing"):
        return (
            "This order cannot be cancelled because "
            "it has already been shipped, delivered, "
            "or cancelled."
        )

    # 7. Prepare draft
    draft = {
        "customer_id": customer_id,
        "order_id": order_id,
        "reason": reason
    }

    print("CANCELLATION DRAFT PREPARED", flush=True)

    # 8. Return draft for confirmation
    return json.dumps({
        "confirmation_required": True,
        "draft": draft
    })

