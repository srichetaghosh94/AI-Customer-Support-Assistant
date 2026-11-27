
from editing.contracts import EditExtraction
from editing.draft_editor import apply_text_edit


# Original ticket draft
original = {
    "customer_id": "test-customer",
    "order_id": None,
    "subject": "Delivery issue",
    "description": "My package arrived."
}


# Test 1: Replace ticket subject
subject_edit = EditExtraction(
    field="subject",
    operation="replace",
    value_provided=True,
    new_value="Damaged product"
)

updated = apply_text_edit(
    "ticket",
    original,
    subject_edit
)

assert updated["subject"] == "Damaged product"
assert original["subject"] == "Delivery issue"

print("[PASS] Ticket subject replacement")


# Test 2: Append ticket description
description_edit = EditExtraction(
    field="description",
    operation="append",
    value_provided=True,
    new_value="The charger was missing."
)

updated_again = apply_text_edit(
    "ticket",
    updated,
    description_edit
)

assert updated_again["description"] == (
    "My package arrived.\n"
    "The charger was missing."
)

print("[PASS] Ticket description append")


# Test 3: Cancellation reason
cancellation = {
    "customer_id": "test-customer",
    "order_id": "test-order",
    "reason": "Changed my mind"
}

reason_edit = EditExtraction(
    field="reason",
    operation="replace",
    value_provided=True,
    new_value="Ordered twice"
)

changed = apply_text_edit(
    "cancellation",
    cancellation,
    reason_edit
)

assert changed["reason"] == "Ordered twice"
assert cancellation["reason"] == "Changed my mind"

print("[PASS] Cancellation reason replacement")


# Test 4: Reject missing values
missing_value = EditExtraction(
    field="reason",
    operation="replace",
    value_provided=False,
    new_value=None
)

try:
    apply_text_edit(
        "cancellation",
        cancellation,
        missing_value
    )
except ValueError:
    print("[PASS] Missing value rejected")
else:
    raise AssertionError("Missing value was accepted")


# Test 5: Reject unsupported edits
invalid_edit = EditExtraction(
    field="customer_id",
    operation="replace",
    value_provided=True,
    new_value="different-customer"
)

try:
    apply_text_edit(
        "ticket",
        original,
        invalid_edit
    )
except ValueError:
    print("[PASS] Customer ID edit rejected")
else:
    raise AssertionError("Customer ID edit was accepted")


print("\nALL 5 DRAFT EDITOR TESTS PASSED")
