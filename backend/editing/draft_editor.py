
from editing.contracts import (
    EditExtraction,
    is_edit_allowed
)
from decimal import Decimal, InvalidOperation
from uuid import UUID


TEXT_FIELDS = {
    "cancellation": {"reason"},
    "refund": {"reason"},
    "ticket": {"subject", "description"}
}


def apply_text_edit(
    draft_type: str,
    draft: dict,
    edit: EditExtraction
) -> dict:

    # Validate draft type and field
    if (
        draft_type not in TEXT_FIELDS
        or edit.field not in TEXT_FIELDS[draft_type]
    ):
        raise ValueError(
            "This field is not supported by the text editor"
        )

    # Check our existing editing policy
    if not is_edit_allowed(
        draft_type,
        edit.field,
        edit.operation
    ):
        raise ValueError(
            "This edit operation is not allowed"
        )

    # Only text replacement and description
    # appending belong in this component
    if edit.operation not in ("replace", "append"):
        raise ValueError(
            "Unsupported text editing operation"
        )

    # No actual value yet: do not change the draft
    if not edit.value_provided or edit.new_value is None:
        raise ValueError(
            "Replacement content is required"
        )

    new_text = edit.new_value.strip()

    if not new_text:
        raise ValueError(
            "Replacement content cannot be empty"
        )

    # Set prototype text limits.
    # Match these to backend/database constraints.
    limits = {
        "reason": 500,
        "subject": 200,
        "description": 5000
    }

    updated_draft = draft.copy()

    if edit.operation == "append":

        old_text = updated_draft.get(
            edit.field
        ) or ""

        if not isinstance(old_text, str):
            raise ValueError(
                "Existing field content must be text"
            )

        updated_text = (
            old_text.rstrip() + "\n" + new_text
            if old_text.strip()
            else new_text
        )

    else:
        updated_text = new_text

    if len(updated_text) > limits[edit.field]:
        raise ValueError(
            "Updated text exceeds the allowed length"
        )

    updated_draft[edit.field] = updated_text

    return updated_draft



def apply_refund_amount_edit(
    draft: dict,
    edit: EditExtraction,
    verified_order: dict
) -> dict:

    # Check the editing policy
    if not is_edit_allowed(
        "refund",
        edit.field,
        edit.operation
    ):
        raise ValueError("Refund edit is not allowed")

    if edit.field != "amount":
        raise ValueError("Expected refund amount edit")

    if edit.operation not in ("replace", "full_refund"):
        raise ValueError("Unsupported amount operation")

    # The caller must supply freshly verified order
    # data from the backend, never from the LLM.
    if (
        str(verified_order.get("order_id"))
        != str(draft.get("order_id"))
    ):
        raise ValueError("Order ID mismatch")

    if (
        str(verified_order.get("customer_id"))
        != str(draft.get("customer_id"))
    ):
        raise ValueError("Customer does not own this order")

    # Match the prototype's refund eligibility rule.
    if verified_order.get("status") not in (
        "shipped",
        "delivered"
    ):
        raise ValueError("Order is not eligible for refund")

    # Read the verified order total
    try:
        order_total = Decimal(
            str(verified_order["total_amount"])
        )
    except (InvalidOperation, KeyError, TypeError):
        raise ValueError("Invalid order total")

    if not order_total.is_finite() or order_total <= 0:
        raise ValueError("Invalid order total")

    # Determine the requested refund amount
    if edit.operation == "full_refund":

        amount = order_total

    else:

        if not edit.value_provided or not edit.new_value:
            raise ValueError("New refund amount is required")

        try:
            amount = Decimal(edit.new_value.strip())
        except InvalidOperation:
            raise ValueError("Invalid refund amount")

    # Monetary safety checks
    if not amount.is_finite():
        raise ValueError("Refund amount must be finite")

    if amount <= 0:
        raise ValueError("Refund amount must be positive")

    if amount > order_total:
        raise ValueError(
            "Refund amount exceeds the order total"
        )

    # Only allow cent-precision values
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError(
            "Refund amount cannot exceed two decimal places"
        )

    # Return a new draft, never modify the original
    updated_draft = draft.copy()

    updated_draft["amount"] = f"{amount:.2f}"

    return updated_draft



# ----------------------------------------
# Unified order ID editing
# ----------------------------------------

def apply_order_id_edit(
    draft_type: str,
    draft: dict,
    edit: EditExtraction,
    verified_order: dict | None = None
) -> dict:

    # Validate request type and editing policy
    if draft_type not in (
        "cancellation",
        "refund",
        "ticket"
    ):
        raise ValueError("Unsupported draft type")

    if edit.field != "order_id":
        raise ValueError("Expected order ID edit")

    if not is_edit_allowed(
        draft_type,
        edit.field,
        edit.operation
    ):
        raise ValueError("Order ID edit is not allowed")

    if not isinstance(draft, dict):
        raise ValueError("Invalid draft")

    try:
        customer_id = UUID(str(draft["customer_id"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("Invalid draft customer ID")

    # ------------------------------------
    # Unlink order from a support ticket
    # ------------------------------------

    if edit.operation == "unlink":

        if edit.value_provided or edit.new_value is not None:
            raise ValueError(
                "Unlink must not include a replacement value"
            )

        updated = draft.copy()
        updated["order_id"] = None

        return updated

    # ------------------------------------
    # Replace order ID
    # ------------------------------------

    if edit.operation != "replace":
        raise ValueError("Unsupported order ID operation")

    if not edit.value_provided or not edit.new_value:
        raise ValueError("New order ID is required")

    # Check UUID format
    try:
        new_order_id = UUID(edit.new_value.strip())
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid order ID format")

    # The caller must fetch this order from
    # the real backend, not from the LLM.
    if not isinstance(verified_order, dict):
        raise ValueError("Verified order data is required")

    try:
        verified_order_id = UUID(
            str(verified_order["order_id"])
        )

        verified_customer_id = UUID(
            str(verified_order["customer_id"])
        )

    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("Invalid verified order data")

    # Verify that the backend returned
    # the exact order requested.
    if verified_order_id != new_order_id:
        raise ValueError("Verified order ID mismatch")

    # Verify ownership
    if verified_customer_id != customer_id:
        raise ValueError(
            "Order does not belong to this customer"
        )

    status = verified_order.get("status")

    # ------------------------------------
    # Cancellation eligibility
    # ------------------------------------

    if draft_type == "cancellation":

        if status not in ("pending", "processing"):
            raise ValueError(
                "New order is not eligible for cancellation"
            )

    # ------------------------------------
    # Refund eligibility
    # ------------------------------------

    if draft_type == "refund":

        if status not in ("shipped", "delivered"):
            raise ValueError(
                "New order is not eligible for refund"
            )

    # ------------------------------------
    # Update a copy of the draft
    # ------------------------------------

    updated = draft.copy()

    # Replacing an ID with the same ID
    # should not unnecessarily reset data.
    if str(updated.get("order_id")) == str(new_order_id):
        return updated

    updated["order_id"] = str(new_order_id)

    # IMPORTANT:
    # Old refund amount belongs to old order.
    # Force a fresh amount selection.
    if draft_type == "refund":
        updated["amount"] = None

    return updated


