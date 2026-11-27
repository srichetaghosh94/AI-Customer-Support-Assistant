
from editing.value_extractor import extract_edit_value


tests = [
    (
        "ticket",
        "description",
        "append",
        "Add Missing charger to my ticket description",
        "Missing charger"
    ),
    (
        "ticket",
        "description",
        "append",
        "I want to add more details to my ticket",
        None
    ),
    (
        "ticket",
        "description",
        "replace",
        "I want to rewrite my ticket description",
        None
    ),
    (
        "ticket",
        "description",
        "replace",
        "Rewrite the description to Package arrived damaged",
        "Package arrived damaged"
    ),
    (
        "refund",
        "amount",
        "replace",
        "Change the refund amount to 25.50",
        "25.50"
    ),
    (
        "refund",
        "reason",
        "replace",
        "Can I change my refund reason first?",
        None
    ),
    (
        "cancellation",
        "reason",
        "replace",
        "Set the cancellation reason to Ordered twice",
        "Ordered twice"
    ),
    (
        "ticket",
        "subject",
        "replace",
        "Change the subject to Delayed delivery",
        "Delayed delivery"
    )
]


passed = 0

print("\nSTARTING UNIVERSAL VALUE TESTS\n")

for index, (
    draft_type,
    field,
    operation,
    message,
    expected
) in enumerate(tests, start=1):

    result = extract_edit_value(
        message=message,
        draft_type=draft_type,
        field=field,
        operation=operation
    )

    success = (
        result.new_value == expected
        and result.value_provided == (expected is not None)
    )

    if success:
        passed += 1

    print(
        f"{index:02}. "
        f"[{'PASS' if success else 'FAIL'}] "
        f"{message}"
    )

    if not success:
        print("    Expected:", repr(expected))
        print("    Predicted:", repr(result))


print("\n================================")
print(f"Total:  {len(tests)}")
print(f"Passed: {passed}")
print(f"Failed: {len(tests) - passed}")
print("================================")
