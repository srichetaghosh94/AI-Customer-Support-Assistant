
from editing.contracts import is_edit_allowed


tests = [

    ("cancellation", "reason", "replace", True),

    ("cancellation", "order_id", "replace", True),

    ("refund", "reason", "replace", True),

    ("refund", "amount", "replace", True),

    ("refund", "amount", "full_refund", True),

    ("refund", "order_id", "replace", True),

    ("ticket", "subject", "replace", True),

    ("ticket", "description", "replace", True),

    ("ticket", "description", "append", True),

    ("ticket", "order_id", "replace", True),

    ("ticket", "order_id", "unlink", True),

    # Operations we intentionally disallow
    ("cancellation", "customer_id", "replace", False),

    ("refund", "customer_id", "replace", False),

    ("ticket", "customer_id", "replace", False),

    ("cancellation", "amount", "replace", False),

    ("refund", "subject", "replace", False),

    ("ticket", "amount", "full_refund", False),

    ("cancellation", "reason", "append", False)
]


passed = 0

print("\nSTARTING EDIT POLICY TESTS\n")

for index, (
    draft_type,
    field,
    operation,
    expected
) in enumerate(tests, start=1):

    actual = is_edit_allowed(
        draft_type,
        field,
        operation
    )

    success = actual == expected

    if success:
        passed += 1

    print(
        f"{index:02}. "
        f"[{'PASS' if success else 'FAIL'}] "
        f"{draft_type} / {field} / {operation}"
    )


print("\n-----------------------------")
print(f"Total tests: {len(tests)}")
print(f"Passed: {passed}")
print(f"Failed: {len(tests) - passed}")
print("-----------------------------")

if passed != len(tests):
    raise SystemExit(1)
