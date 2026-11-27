
from editing.contracts import EditExtraction
from editing.draft_editor import apply_order_id_edit


CUSTOMER = "11111111-1111-4111-8111-111111111111"
OTHER_CUSTOMER = "22222222-2222-4222-8222-222222222222"

OLD_ORDER = "33333333-3333-4333-8333-333333333333"
NEW_ORDER = "44444444-4444-4444-8444-444444444444"


cancellation = {
    "customer_id": CUSTOMER,
    "order_id": OLD_ORDER,
    "reason": "Changed my mind"
}

refund = {
    "customer_id": CUSTOMER,
    "order_id": OLD_ORDER,
    "amount": "35.00",
    "reason": "Product damaged"
}

ticket = {
    "customer_id": CUSTOMER,
    "order_id": OLD_ORDER,
    "subject": "Delivery issue",
    "description": "Package arrived damaged"
}


def make_edit(value=None, operation="replace"):
    return EditExtraction(
        field="order_id",
        operation=operation,
        value_provided=value is not None,
        new_value=value
    )


def order_data(status, customer=CUSTOMER, order=NEW_ORDER):
    return {
        "order_id": order,
        "customer_id": customer,
        "status": status,
        "total_amount": "100.00"
    }


def expect_rejected(name, draft_type, draft, edit, verified=None):
    try:
        apply_order_id_edit(
            draft_type,
            draft,
            edit,
            verified
        )
    except ValueError:
        print(f"[PASS] {name}")
    else:
        raise AssertionError(f"{name} was accepted")


# 1. Change cancellation order
updated = apply_order_id_edit(
    "cancellation",
    cancellation,
    make_edit(NEW_ORDER),
    order_data("processing")
)

assert updated["order_id"] == NEW_ORDER
assert updated["reason"] == "Changed my mind"
assert cancellation["order_id"] == OLD_ORDER
print("[PASS] Cancellation order ID changed")


# 2. Change refund order and reset amount
updated = apply_order_id_edit(
    "refund",
    refund,
    make_edit(NEW_ORDER),
    order_data("delivered")
)

assert updated["order_id"] == NEW_ORDER
assert updated["amount"] is None
assert updated["reason"] == "Product damaged"
assert refund["amount"] == "35.00"
print("[PASS] Refund order changed and amount reset")


# 3. Change support ticket order
updated = apply_order_id_edit(
    "ticket",
    ticket,
    make_edit(NEW_ORDER),
    order_data("delivered")
)

assert updated["order_id"] == NEW_ORDER
assert updated["subject"] == ticket["subject"]
print("[PASS] Ticket order ID changed")


# 4. Unlink ticket order
updated = apply_order_id_edit(
    "ticket",
    ticket,
    make_edit(operation="unlink")
)

assert updated["order_id"] is None
assert ticket["order_id"] == OLD_ORDER
print("[PASS] Ticket order unlinked")


# 5. Reject invalid UUID
expect_rejected(
    "Invalid UUID rejected",
    "refund",
    refund,
    make_edit("not-a-valid-uuid"),
    order_data("delivered")
)


# 6. Reject missing replacement
expect_rejected(
    "Missing order ID rejected",
    "cancellation",
    cancellation,
    make_edit(),
    order_data("pending")
)


# 7. Reject mismatched backend order
expect_rejected(
    "Mismatched order rejected",
    "cancellation",
    cancellation,
    make_edit(NEW_ORDER),
    order_data("pending", order=OLD_ORDER)
)


# 8. Reject another customer's order
expect_rejected(
    "Wrong customer rejected",
    "refund",
    refund,
    make_edit(NEW_ORDER),
    order_data("delivered", customer=OTHER_CUSTOMER)
)


# 9. Reject ineligible cancellation
expect_rejected(
    "Delivered cancellation rejected",
    "cancellation",
    cancellation,
    make_edit(NEW_ORDER),
    order_data("delivered")
)


# 10. Reject ineligible refund
expect_rejected(
    "Pending refund rejected",
    "refund",
    refund,
    make_edit(NEW_ORDER),
    order_data("pending")
)


# 11. Reject cancellation unlink
expect_rejected(
    "Cancellation unlink rejected",
    "cancellation",
    cancellation,
    make_edit(operation="unlink")
)


# 12. Reject missing backend verification
expect_rejected(
    "Missing order verification rejected",
    "ticket",
    ticket,
    make_edit(NEW_ORDER)
)


# 13. Same refund order preserves amount
same_order = apply_order_id_edit(
    "refund",
    refund,
    make_edit(OLD_ORDER),
    order_data("delivered", order=OLD_ORDER)
)

assert same_order["amount"] == "35.00"
print("[PASS] Unchanged refund order preserves amount")


print("\nALL 13 ORDER ID EDITOR TESTS PASSED")
