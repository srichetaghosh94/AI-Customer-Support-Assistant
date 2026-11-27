
from editing.edit_extractor import (
    extract_edit_request
)

from editing.contracts import is_edit_allowed


ORDER_A = "30b04a44-cdfe-47f2-86ba-01435505f4f6"
ORDER_B = "8be96309-91ce-4f01-8368-3aebfa3ee777"


# Each case contains:
# draft_type, message, field, operation,
# new_value, allowed

tests = [

    # ----------------------------------
    # CANCELLATION
    # ----------------------------------

    (
        "cancellation",
        "Can I change the cancellation reason first?",
        "reason",
        "replace",
        None,
        True
    ),

    (
        "cancellation",
        "Change the cancellation reason to Ordered twice",
        "reason",
        "replace",
        "Ordered twice",
        True
    ),

    (
        "cancellation",
        "no i wanna change the reason first",
        "reason",
        "replace",
        None,
        True
    ),

    (
        "cancellation",
        "I entered the wrong order ID",
        "order_id",
        "replace",
        None,
        True
    ),

    (
        "cancellation",
        f"Change the order ID to {ORDER_A}",
        "order_id",
        "replace",
        ORDER_A,
        True
    ),

    (
        "cancellation",
        "I want to change the cancellation request",
        "unknown",
        "unknown",
        None,
        False
    ),

    (
        "cancellation",
        "Change my customer ID",
        "customer_id",
        "replace",
        None,
        False
    ),

    # ----------------------------------
    # REFUND
    # ----------------------------------

    (
        "refund",
        "Can I change the refund reason?",
        "reason",
        "replace",
        None,
        True
    ),

    (
        "refund",
        "Set the refund reason to Damaged packaging",
        "reason",
        "replace",
        "Damaged packaging",
        True
    ),

    (
        "refund",
        "Change the refund amount to 25.50",
        "amount",
        "replace",
        "25.50",
        True
    ),

    (
        "refund",
        "I want to change my refund amount",
        "amount",
        "replace",
        None,
        True
    ),

    (
        "refund",
        "Actually make it a full refund",
        "amount",
        "full_refund",
        None,
        True
    ),

    (
        "refund",
        "I'd rather request a full refund",
        "amount",
        "full_refund",
        None,
        True
    ),

    (
        "refund",
        "I gave the wrong order ID for the refund",
        "order_id",
        "replace",
        None,
        True
    ),

    (
        "refund",
        f"Replace the refund order ID with {ORDER_B}",
        "order_id",
        "replace",
        ORDER_B,
        True
    ),

    (
        "refund",
        "Change my customer ID instead",
        "customer_id",
        "replace",
        None,
        False
    ),

    (
        "refund",
        "I need to edit something",
        "unknown",
        "unknown",
        None,
        False
    ),

    # ----------------------------------
    # SUPPORT TICKET
    # ----------------------------------

    (
        "ticket",
        "Change the ticket subject to Delayed delivery",
        "subject",
        "replace",
        "Delayed delivery",
        True
    ),

    (
        "ticket",
        "Can I update the ticket subject?",
        "subject",
        "replace",
        None,
        True
    ),

    (
        "ticket",
        "Rewrite the ticket description to Package arrived damaged",
        "description",
        "replace",
        "Package arrived damaged",
        True
    ),

    (
        "ticket",
        "I want to rewrite my ticket description",
        "description",
        "replace",
        None,
        True
    ),

    (
        "ticket",
        "Add Missing charger to my ticket description",
        "description",
        "append",
        "Missing charger",
        True
    ),

    (
        "ticket",
        "I want to add more details to my ticket",
        "description",
        "append",
        None,
        True
    ),

    (
        "ticket",
        f"Change the linked order ID to {ORDER_A}",
        "order_id",
        "replace",
        ORDER_A,
        True
    ),

    (
        "ticket",
        "Remove the order ID from this support ticket",
        "order_id",
        "unlink",
        None,
        True
    ),

    (
        "ticket",
        "I want to link a different order",
        "order_id",
        "replace",
        None,
        True
    ),

    (
        "ticket",
        "I want to change the customer ID",
        "customer_id",
        "replace",
        None,
        False
    ),

    (
        "ticket",
        "I want to change the ticket",
        "unknown",
        "unknown",
        None,
        False
    )
]


passed = 0

print("\nSTARTING UNIVERSAL EDIT EVALUATION\n")

for index, case in enumerate(tests, start=1):

    (
        draft_type,
        message,
        expected_field,
        expected_operation,
        expected_value,
        expected_allowed
    ) = case

    try:

        result = extract_edit_request(
            message=message,
            draft_type=draft_type
        )

        actual_allowed = is_edit_allowed(
            draft_type,
            result.field,
            result.operation
        )


        success = (
            result.field == expected_field
            and result.operation == expected_operation
            and result.value_provided == (
                expected_value is not None
            )
            and result.new_value == expected_value
            and actual_allowed == expected_allowed
        )

        if success:
            passed += 1

        print(
            f"{index:02}. "
            f"[{'PASS' if success else 'FAIL'}] "
            f"{message}"
        )

        if not success:
            print(
                "    Expected:",
                (
                    expected_field,
                    expected_operation,
                    expected_value,
                    expected_allowed
                )
            )

            print(
                "    Predicted:",
                (
                    result.field,
                    result.operation,
                    result.new_value,
                    actual_allowed
                )
            )

    except Exception as exc:

        print(
            f"{index:02}. [ERROR] {message}"
        )

        print(
            "    Error:",
            repr(exc)
        )


print("\n====================================")
print("UNIVERSAL EDIT RESULTS")
print("====================================")
print(f"Total tests: {len(tests)}")
print(f"Correct:     {passed}")
print(f"Failed:      {len(tests) - passed}")
print(
    f"Accuracy:    "
    f"{passed / len(tests) * 100:.2f}%"
)
print("====================================")

if passed != len(tests):
    raise SystemExit(1)
