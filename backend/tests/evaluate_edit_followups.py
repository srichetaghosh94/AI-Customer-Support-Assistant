
from editing.followup_extractor import (
    extract_edit_followup
)


ORDER_ID = "30b04a44-cdfe-47f2-86ba-01435505f4f6"


tests = [
    (
        "cancellation", "reason", "replace",
        "Ordered twice",
        "provide_value", "Ordered twice"
    ),
    (
        "refund", "reason", "replace",
        "Damaged packaging",
        "provide_value", "Damaged packaging"
    ),
    (
        "refund", "amount", "replace",
        "25.50",
        "provide_value", "25.50"
    ),
    (
        "ticket", "subject", "replace",
        "Delayed delivery",
        "provide_value", "Delayed delivery"
    ),
    (
        "ticket", "description", "append",
        "The charger was missing.",
        "provide_value", "The charger was missing."
    ),
    (
        "ticket", "order_id", "replace",
        ORDER_ID,
        "provide_value", ORDER_ID
    ),
    (
        "cancellation", "reason", "replace",
        "Never mind, keep the original reason.",
        "stop_editing", None
    ),
    (
        "refund", "amount", "replace",
        "Go ahead and submit it",
        "unclear", None
    ),
    (
        "ticket", "description", "append",
        "What was my original description?",
        "unclear", None
    ),
    (
        "cancellation", "order_id", "replace",
        "Yes",
        "unclear", None
    )
]


passed = 0

print("\nSTARTING UNIFIED FOLLOW-UP EVALUATION\n")

for index, (
    draft_type,
    field,
    operation,
    message,
    expected_decision,
    expected_value
) in enumerate(tests, start=1):

    try:
        result = extract_edit_followup(
            message=message,
            draft_type=draft_type,
            field=field,
            operation=operation
        )

        success = (
            result.decision == expected_decision
            and result.new_value == expected_value
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
                expected_decision,
                repr(expected_value)
            )
            print(
                "    Predicted:",
                result
            )

    except Exception as exc:
        print(
            f"{index:02}. [ERROR] "
            f"{message}: {repr(exc)}"
        )


print("\n================================")
print(f"Total:  {len(tests)}")
print(f"Passed: {passed}")
print(f"Failed: {len(tests) - passed}")
print("================================")

if passed != len(tests):
    raise SystemExit(1)
