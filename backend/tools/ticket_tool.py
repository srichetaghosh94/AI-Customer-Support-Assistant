
import json
from uuid import UUID

import httpx
from langchain_core.tools import tool
import json
from uuid import UUID


@tool
def get_ticket_details(ticket_id: str) -> str:
    """
    Retrieve the status and details of an existing
    customer support ticket using its ticket UUID.

    Use when customers ask about an existing ticket,
    its status, subject, or description.

    Requires a ticket UUID, not an order UUID.
    """

    print(f"TICKET TOOL STARTED: {ticket_id}", flush=True)

    # 1. Validate the ticket UUID
    try:
        ticket_id = str(UUID(ticket_id))
    except ValueError:
        return "Invalid ticket ID. Please provide a valid UUID."

    # 2. Call our existing FastAPI endpoint
    try:
        response = httpx.get(
            f"http://127.0.0.1:8000/tickets/{ticket_id}",
            timeout=10.0
        )

        if response.status_code == 404:
            return "No support ticket was found with that ID."

        response.raise_for_status()

    except httpx.HTTPError:
        return "Unable to retrieve the support ticket right now."

    # 3. Return ticket details to the LLM
    ticket = response.json()

    print(f"TICKET TOOL CALLED: {ticket_id}", flush=True)

    return json.dumps(ticket)


@tool
def prepare_support_ticket(
    customer_id: str,
    subject: str,
    description: str,
    order_id: str | None = None
) -> str:
    """
    Prepare a new customer support ticket draft.

    Use when a customer wants to raise a complaint,
    report a problem, or create a support ticket.

    Required information:
    - customer_id: Customer UUID
    - subject: Short summary of the problem
    - description: Details of the problem

    Optional:
    - order_id: Related order UUID

    Ask for missing required information before
    calling this tool.

    This tool does NOT create a database record.
    It only prepares a draft for customer confirmation.
    """

    # 1. Validate customer ID
    try:
        customer_id = str(UUID(customer_id))
    except (ValueError, TypeError):
        return "Invalid customer ID."

    # 2. Validate optional order ID
    if order_id:
        try:
            order_id = str(UUID(order_id))
        except (ValueError, TypeError):
            return "Invalid order ID."

    # 3. Validate the ticket content
    subject = subject.strip()
    description = description.strip()

    if not subject or len(subject) > 200:
        return "Subject must contain 1 to 200 characters."

    if not description:
        return "Ticket description cannot be empty."

    # 4. Prepare the draft
    draft = {
        "customer_id": customer_id,
        "order_id": order_id,
        "subject": subject,
        "description": description
    }

    print("SUPPORT TICKET DRAFT PREPARED", flush=True)

    # 5. Return the draft to the chatbot
    return json.dumps({
        "confirmation_required": True,
        "draft": draft
    })

