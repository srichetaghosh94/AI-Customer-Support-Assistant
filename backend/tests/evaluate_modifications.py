
import csv
from pathlib import Path

from modification_classifier import detect_modification


# -----------------------------------
# 1. Test cases
# -----------------------------------

TEST_CASES = [

    # ==================================
    # MODIFICATION REQUESTS
    # ==================================

    ("Can you change the refund amount?", "modify"),
    ("Can I change the reason first?", "modify"),
    ("I need to update the refund amount", "modify"),
    ("Can we correct the order ID?", "modify"),
    ("Change the reason before submitting", "modify"),
    ("Yes, but update the amount first", "modify"),
    ("Could I edit my cancellation reason?", "modify"),
    ("Replace the reason with: Ordered twice", "modify"),
    ("Actually use the reason I changed my mind", "modify"),
    ("Update my refund amount to 25.00", "modify"),
    ("I want to change the ticket description", "modify"),
    ("Please fix the customer ID before submitting", "modify"),
    ("Can u chnge the reason pls?", "modify"),
    ("Change the reason and then submit it", "modify"),

    # ==================================
    # NOT MODIFICATION REQUESTS
    # ==================================

    ("Yes, please submit it", "not_modify"),
    ("Go ahead", "not_modify"),
    ("Go aheadd please", "not_modify"),
    ("Affirmative", "not_modify"),
    ("Okay, do it", "not_modify"),
    ("No", "not_modify"),
    ("No thanks", "not_modify"),
    ("Don't submit it", "not_modify"),
    ("Actually, cancel that", "not_modify"),
    ("I changed my mind, forget it", "not_modify"),
    ("Please discard this draft", "not_modify"),
    ("Don't change anything, just submit it", "not_modify"),
    ("What happens after I submit?", "not_modify"),
    ("Can you explain the process?", "not_modify"),
    ("Can I review the draft again?", "not_modify"),

    # ==================================
    # UNCERTAIN INTENT
    # ==================================

    ("Wait, I made a mistake", "uncertain"),
    ("Something is wrong with the details", "uncertain"),
    ("Hmm, about that amount...", "uncertain"),
    ("There is an issue with my request", "uncertain"),
]


# -----------------------------------
# 2. Run evaluation
# -----------------------------------

def run_evaluation():

    results = []
    correct = 0

    print("\nSTARTING MODIFICATION EVALUATION\n")

    for index, (message, expected) in enumerate(
        TEST_CASES,
        start=1
    ):

        error = ""

        try:
            predicted = detect_modification(message)

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

    # -----------------------------------
    # 3. Evaluation metrics
    # -----------------------------------

    total = len(TEST_CASES)

    accuracy = (
        correct / total * 100
        if total
        else 0
    )

    false_modifications = sum(
        1 for result in results
        if result["predicted"] == "modify"
        and result["expected"] != "modify"
    )

    missed_modifications = sum(
        1 for result in results
        if result["expected"] == "modify"
        and result["predicted"] != "modify"
    )

    print("\n" + "=" * 45)
    print("MODIFICATION EVALUATION RESULTS")
    print("=" * 45)

    print(f"Total tests:          {total}")
    print(f"Correct predictions:  {correct}")
    print(f"Failed predictions:   {total - correct}")
    print(f"Accuracy:             {accuracy:.2f}%")
    print(f"False modifications:  {false_modifications}")
    print(f"Missed modifications: {missed_modifications}")

    # -----------------------------------
    # 4. Save CSV
    # -----------------------------------

    output_file = Path(__file__).with_name(
        "modification_results_v1.csv"
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
