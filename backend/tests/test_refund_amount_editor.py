
from editing.contracts import EditExtraction
from editing.draft_editor import apply_refund_amount_edit


draft = {
    "customer_id": "customer-123",
    "order_id": "order-456",
    "reason": "Damaged product",
    "amount": "20.00"
}

verified_order = {
    "customer_id": "customer-123",
    "order_id": "order-456",
    "status": "delivered",
    "total_amount": "100.00"
}


def make_edit(operation, value=None):
    return EditExtraction(
        field="amount",
        operation=operation,
        value_provided=value is not None,
        new_value=value
    )


def expect_rejected(name, edit, order=None):
    try:
        apply_refund_amount_edit(
            draft,
            edit,
            order or verified_order
        )
    except ValueError:
        print(f"[PASS] {name}")
    else:
        raise AssertionError(f"{name} was accepted")


# Test 1: Partial refund
updated = apply_refund_amount_edit(
    draft,
    make_edit("replace", "35.50"),
    verified_order
)

assert updated["amount"] == "35.50"
assert draft["amount"] == "20.00"
print("[PASS] Partial refund updated")


# Test 2: Full refund
updated = apply_refund_amount_edit(
    draft,
    make_edit("full_refund"),
    verified_order
)

assert updated["amount"] == "100.00"
print("[PASS] Full refund calculated")


# Test 3: Excessive amount
expect_rejected(
    "Excessive refund rejected",
    make_edit("replace", "150.00")
)


# Test 4: Negative amount
expect_rejected(
    "Negative refund rejected",
    make_edit("replace", "-10.00")
)


# Test 5: Missing amount
expect_rejected(
    "Missing refund amount rejected",
    make_edit("replace")
)


# Test 6: Invalid decimal precision
expect_rejected(
    "Excess decimal precision rejected",
    make_edit("replace", "25.555")
)


# Test 7: Wrong customer
expect_rejected(
    "Wrong customer rejected",
    make_edit("replace", "25.00"),
    {**verified_order, "customer_id": "other-customer"}
)


# Test 8: Ineligible order status
expect_rejected(
    "Ineligible order rejected",
    make_edit("replace", "25.00"),
    {**verified_order, "status": "pending"}
)


# Test 9: Mismatched order ID
expect_rejected(
    "Wrong order rejected",
    make_edit("replace", "25.00"),
    {**verified_order, "order_id": "another-order"}
)


# Test 10: Invalid non-finite amount
expect_rejected(
    "NaN refund rejected",
    make_edit("replace", "NaN")
)


print("\nALL 10 REFUND AMOUNT TESTS PASSED")
