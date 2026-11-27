
import csv
from pathlib import Path

from routers.chat import confirmation_llm
from confirmation_prompt import CONFIRMATION_SYSTEM_PROMPT


# -----------------------------------
# 1. Current classifier instructions
# -----------------------------------

# Keep this identical to the system prompt
# currently used for confirmation_llm
# inside routers/chat.py.


# -----------------------------------
# 2. Test cases
# -----------------------------------

# Each tuple contains:
# (customer message, expected intent)
#
# These examples are TEST DATA.
# They are NOT hardcoded chatbot rules.

TEST_CASES = [

    # CONFIRMATIONS
    ("Yes, please submit it", "confirm"),
    ("Go ahead", "confirm"),
    ("Go aheadd please", "confirm"),
    ("Affirmative", "confirm"),
    ("Sure, proceed", "confirm"),
    ("Okay, do it", "confirm"),
    ("I approve the request", "confirm"),
    ("You can send it now", "confirm"),
    ("That looks good, submit it", "confirm"),
    ("Yep, let's do it", "confirm"),
    ("Everything looks correct, proceed", "confirm"),
    ("Pls go ahed and send it", "confirm"),

    # CANCELLATIONS
    ("No", "cancel"),
    ("No thanks", "cancel"),
    ("Don't submit it", "cancel"),
    ("Actually, cancel that", "cancel"),
    ("I changed my mind, forget it", "cancel"),
    ("Please discard this draft", "cancel"),
    ("Stop, I don't want to submit", "cancel"),
    ("Nope, don't proceed", "cancel"),
    ("I no longer want to submit it", "cancel"),
    ("Please don't send this request", "cancel"),
    ("I don't want this request anymore", "cancel"),
    ("Please withdraw the request", "cancel"),
    ("Forget the whole thing", "cancel"),

    # UNCLEAR / NEEDS CLARIFICATION
    ("Maybe", "unclear"),
    ("I'm not sure yet", "unclear"),
    ("Can you change the amount?", "unclear"),
    ("What happens after I submit?", "unclear"),
    ("Can I change the reason first?", "unclear"),
    ("Wait, I have a question", "unclear"),
    ("Let me think about it", "unclear"),
    ("Can you explain the process?", "unclear"),
    ("I need to review the details", "unclear"),
    ("What is the refund policy?", "unclear"),


    # NEW TEST CASES: MODIFICATIONS
    ("I need to update the refund amount", "unclear"),
    ("Can we correct the order ID?", "unclear"),
    ("Change the reason before submitting", "unclear"),
    ("Yes, but update the amount first", "unclear"),
    ("Wait, I made a mistake in the details", "unclear"),
    
]


# -----------------------------------
# 3. Run a single classification
# -----------------------------------

def classify_message(message: str) -> str:

    response = confirmation_llm.invoke([
        ("system", CONFIRMATION_SYSTEM_PROMPT),
        ("human", message)
    ])

    return response.decision


# -----------------------------------
# 4. Evaluate all test messages
# -----------------------------------

def run_evaluation():

    results = []
    correct = 0

    print("\nSTARTING CONFIRMATION EVALUATION\n")

    for index, (message, expected) in enumerate(
        TEST_CASES, start=1
    ):

        error = ""

        try:
            predicted = classify_message(message)

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
            f"{index:02d}. [{status}] "
            f"{message}\n"
            f"    Expected: {expected} | "
            f"Predicted: {predicted}"
        )

    # -----------------------------------
    # 5. Calculate evaluation metrics
    # -----------------------------------

    total = len(TEST_CASES)
    accuracy = (correct / total) * 100

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

    print("\n" + "=" * 45)
    print("EVALUATION RESULTS")
    print("=" * 45)

    print(f"Total tests:          {total}")
    print(f"Correct predictions:  {correct}")
    print(f"Failed predictions:   {total - correct}")
    print(f"Accuracy:             {accuracy:.2f}%")
    print(f"False confirmations:  {false_confirmations}")
    print(f"False cancellations:  {false_cancellations}")

    # -----------------------------------
    # 6. Save results to CSV
    # -----------------------------------

    output_file = Path(__file__).with_name(
        "confirmation_results_v3.csv"
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
