
from cancellation_edit_extractor import extract_cancellation_edit


# -----------------------------------
# Test cases
# (message, expected action, expected reason)
# -----------------------------------

TEST_CASES = [

    (
        "Can I change the cancellation reason first?",
        "edit_reason",
        None
    ),

    (
        "Change the reason to Ordered twice",
        "edit_reason",
        "Ordered twice"
    ),

    (
        "Actually use 'I changed my mind' as my reason",
        "edit_reason",
        "I changed my mind"
    ),

    (
        "Replace the reason with: Wrong item selected",
        "edit_reason",
        "Wrong item selected"
    ),

    (
        "Can you edit the reason?",
        "edit_reason",
        None
    ),

    (
        "Update the reason to duplicate order, then submit",
        "edit_reason",
        "duplicate order"
    ),

    (
        "Please correct my order ID",
        "other_field",
        None
    ),

    (
        "Change my customer ID before submitting",
        "other_field",
        None
    ),

    (
        "I want to change the cancellation request",
        "unclear",
        None
    ),

    (
        "I need to edit something",
        "unclear",
        None
    ),


    # ==========================================
    # NEW UNSEEN EXTRACTION TESTS
    # ==========================================

    (
        "I want to change the reason but haven't decided what to write yet",
        "edit_reason",
        None
    ),

    (
        "Set my cancellation reason to: I placed the order accidentally",
        "edit_reason",
        "I placed the order accidentally"
    ),

    (
        "Please use 'Ordered the wrong size' as the new reason",
        "edit_reason",
        "Ordered the wrong size"
    ),

    (
        "Update the reason to Duplicate purchase, then send the request",
        "edit_reason",
        "Duplicate purchase"
    ),

    (
        "I need to correct the order number",
        "other_field",
        None
    ),

    (
        "Can I change my customer ID instead?",
        "other_field",
        None
    ),

    (
        "There's a mistake somewhere in my request",
        "unclear",
        None
    ),

    (
        "I want to update something before approving",
        "unclear",
        None
    ),

    (
        "Actually I would wanna change the reason of cancellation first",
        "edit_reason",
        None
    ),

    (
        "no i wanna change the reason first",
        "edit_reason",
        None
    ),

]


# -----------------------------------
# Run evaluation
# -----------------------------------

def run_evaluation():

    correct = 0

    print("\nSTARTING CANCELLATION EDIT EVALUATION\n")

    for index, (
        message,
        expected_action,
        expected_reason
    ) in enumerate(TEST_CASES, start=1):

        try:
            result = extract_cancellation_edit(message)

            action = result.action
            reason = result.new_reason

            passed = (
                action == expected_action
                and reason == expected_reason
            )

        except Exception as exc:
            action = "error"
            reason = str(exc)
            passed = False

        if passed:
            correct += 1

        print(
            f"{index:02d}. "
            f"[{'PASS' if passed else 'FAIL'}] "
            f"{message}"
        )

        print(
            f"    Expected: {expected_action}, "
            f"{expected_reason!r}"
        )

        print(
            f"    Predicted: {action}, "
            f"{reason!r}\n"
        )

    total = len(TEST_CASES)

    print("=" * 45)
    print("CANCELLATION EDIT RESULTS")
    print("=" * 45)

    print(f"Total tests: {total}")
    print(f"Correct:     {correct}")
    print(f"Failed:      {total - correct}")
    print(f"Accuracy:    {correct / total * 100:.2f}%")


if __name__ == "__main__":
    run_evaluation()
