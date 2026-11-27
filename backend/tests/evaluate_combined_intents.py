
import csv
from pathlib import Path

from modification_classifier import detect_modification
from routers.chat import confirmation_llm
from confirmation_prompt import CONFIRMATION_SYSTEM_PROMPT


# -----------------------------------
# 1. Combined classification pipeline
# -----------------------------------

def classify_combined(message: str) -> str:

    # Stage 1: Check whether customer wants an edit
    modification_decision = detect_modification(message)

    if modification_decision == "modify":
        return "modify"

    # Never submit or discard when editing intent
    # cannot be determined confidently
    if modification_decision == "uncertain":
        return "unclear"

    if modification_decision != "not_modify":
        return "unclear"

    # Stage 2: Reuse our working V3 classifier
    confirmation_result = confirmation_llm.invoke([
        ("system", CONFIRMATION_SYSTEM_PROMPT),
        ("human", message)
    ])

    return confirmation_result.decision


# -----------------------------------
# 2. Fresh test cases
# -----------------------------------

TEST_CASES = [

    # CONFIRM
    ("All set, please file the ticket.", "confirm"),
    ("Okay, send the refund request through.", "confirm"),
    ("Looks right to me. You can put it in.", "confirm"),
    ("Yep, submit the cancellation request.", "confirm"),
    ("Sure thing, please proceed now.", "confirm"),
    ("That draft is fine; send it.", "confirm"),
    ("Perfect, make the request official.", "confirm"),
    ("Yup go for it plz", "confirm"),

    # CANCEL
    ("Please scrap this draft.", "cancel"),
    ("I don't want to file that ticket after all.", "cancel"),
    ("Withdraw my request before it is sent.", "cancel"),
    ("Please leave it unsubmitted and discard it.", "cancel"),
    ("Do not send that refund request.", "cancel"),
    ("I no longer want to make this cancellation request.", "cancel"),
    ("Delete this draft instead of submitting it.", "cancel"),
    ("No, forget the draft entirely.", "cancel"),

    # MODIFY
    ("Could we change the cancellation reason to 'ordered twice'?", "modify"),
    ("Before sending, set the refund amount to 19.99.", "modify"),
    ("Yes, but replace the subject first.", "modify"),
    ("Actually, use 'I changed my mind' as my reason.", "modify"),
    ("Please don't submit yet, change the description.", "modify"),
    ("Can u fix the order id?", "modify"),
    ("Keep the request but update the amount.", "modify"),
    ("Instead of 'damaged', write 'wrong size' in the reason.", "modify"),

    # UNCLEAR
    ("Could you show the draft again?", "unclear"),
    ("I think I need a moment.", "unclear"),
    ("What's the next step if I say yes?", "unclear"),
    ("Does this request get approved automatically?", "unclear"),
    ("Something about this looks off.", "unclear"),
    ("Can you tell me the amount again?", "unclear"),
    ("Hold on, I have another question.", "unclear"),
    ("I'm not ready to decide.", "unclear"),
]


# -----------------------------------
# 3. Evaluate the combined pipeline
# -----------------------------------

def run_evaluation():

    results = []
    correct = 0

    print("\nSTARTING COMBINED INTENT EVALUATION\n")

    for index, (message, expected) in enumerate(
        TEST_CASES,
        start=1
    ):

        error = ""

        try:
            predicted = classify_combined(message)

        except Exception as exc:
            predicted = "error"
            error = str(exc)

        passed = predicted == expected

        if passed:
            correct += 1

        results.append({
            "message": message,
            "expected": expected,
            "predicted": predicted,
            "passed": passed,
            "error": error
        })

        status = "PASS" if passed else "FAIL"

        print(
            f"{index:02d}. [{status}] {message}\n"
            f"    Expected: {expected} | "
            f"Predicted: {predicted}"
        )

    total = len(TEST_CASES)

    false_confirmations = sum(
        1 for result in results
        if result["predicted"] == "confirm"
        and result["expected"] != "confirm"
    )

    false_cancellations = sum(
        1 for result in results
        if result["predicted"] == "cancel"
        and result["expected"] != "cancel"
    )

    missed_modifications = sum(
        1 for result in results
        if result["expected"] == "modify"
        and result["predicted"] != "modify"
    )

    print("\n" + "=" * 45)
    print("COMBINED INTENT EVALUATION RESULTS")
    print("=" * 45)

    print(f"Total tests:          {total}")
    print(f"Correct predictions:  {correct}")
    print(f"Failed predictions:   {total - correct}")
    print(f"Accuracy:             {correct / total * 100:.2f}%")
    print(f"False confirmations:  {false_confirmations}")
    print(f"False cancellations:  {false_cancellations}")
    print(f"Missed modifications: {missed_modifications}")

    # Save results for later comparisons
    output_file = Path(__file__).with_name(
        "combined_results_v1.csv"
    )

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "message",
                "expected",
                "predicted",
                "passed",
                "error"
            ]
        )

        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    run_evaluation()
