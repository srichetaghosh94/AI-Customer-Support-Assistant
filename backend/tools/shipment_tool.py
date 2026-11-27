
import json
from uuid import UUID

import httpx
from langchain_core.tools import tool


@tool
def get_shipment_details(order_id: str) -> str:
    """
    Retrieve the shipping and delivery information
    for a customer order using its order UUID.

    Use this tool when a customer asks about:
    - Shipment status
    - Package tracking
    - Delivery date
    - Shipping carrier
    - Tracking number
    - Where their package is

    The input must be the order UUID, not a shipment UUID.
    """

    print(f"SHIPMENT TOOL STARTED: {order_id}", flush=True)

    # 1. Validate the order UUID
    try:
        order_id = str(UUID(order_id))
    except ValueError:
        return "Invalid order ID. Please provide a valid UUID."

    # 2. Call the existing shipment API
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/orders/{order_id}/shipment",
            timeout=10.0
        )

        if response.status_code == 404:
            return (
                "No shipment information was found "
                "for this order."
            )

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve shipment information right now."

    # 3. Read shipment data from the API
    shipment = response.json()

    print(f"SHIPMENT TOOL CALLED: {order_id}", flush=True)

    # 4. Return information to the LLM
    return json.dumps({
        "order_id": shipment["order_id"],
        "shipment_id": shipment["shipment_id"],
        "status": shipment["status"],
        "carrier": shipment["carrier"],
        "tracking_number": shipment["tracking_number"],
        "estimated_delivery": shipment["estimated_delivery"],
        "delivered_at": shipment["delivered_at"]
    })
