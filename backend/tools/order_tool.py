
import json
from uuid import UUID

import httpx
from langchain_core.tools import tool


@tool
def get_order_details(order_id: str) -> str:
    """
    Get the details and status of a customer order.
    Use this tool when the customer asks about an order
    and provides an order UUID.
    """
    print(f"ORDER TOOL STARTED: {order_id}", flush=True)
    # 1. Validate the order UUID
    try:
        order_id = str(UUID(order_id))
    except ValueError:
        return "Invalid order ID. Please provide a valid UUID."

    # 2. Call our existing FastAPI orders endpoint
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/orders/{order_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            return "No order was found with that order ID."

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve the order right now."

    # 3. Return the real order details
    order = response.json()

    print(f"ORDER TOOL CALLED: {order_id}")

    return json.dumps({
        "order_id": order["order_id"],
        "status": order["status"],
        "total_amount": order["total_amount"],
        "items": order["items"]
    })
