
from typing import Literal

from pydantic import BaseModel
from langchain_ollama import ChatOllama


# -----------------------------------
# 1. Extraction schema
# -----------------------------------

class CancellationEditExtraction(BaseModel):

    action: Literal[
        "edit_reason",
        "other_field",
        "unclear"
    ]

    new_reason: str | None = None


# -----------------------------------
# 2. Extraction instructions
# -----------------------------------


CANCELLATION_EDIT_PROMPT = """
You are an information extraction assistant.

CONTEXT:
A customer has an order cancellation request
draft that has NOT been submitted.

A separate classifier has detected a possible
modification request.

YOUR TASK:
Identify which field the customer wants
to modify and extract any replacement reason.

Return one of three actions:

1. edit_reason

Use ONLY when the customer clearly identifies
the cancellation REASON as the field to edit.

If the customer provides a replacement reason,
copy that reason faithfully from their message
into new_reason.

If the customer only asks whether they can
change the reason, set new_reason to null.

2. other_field

Use when the customer clearly wants to
change a field other than the reason.

For example:
- Order ID
- Customer ID

Set new_reason to null.

3. unclear

Use when the customer wants to change the
request but does not specify which field.

Do not assume that changing a cancellation
request means changing its reason.

Set new_reason to null.


FIELD IDENTIFICATION RULES:

Always identify the field being modified
BEFORE extracting a replacement value.

1. If the customer explicitly wants to
change the cancellation REASON,
choose edit_reason.

2. If the customer explicitly wants to
change another field, such as an order
identifier or customer identifier,
choose other_field.

3. If the customer wants to change the
request but does not identify the field,
choose unclear.

Do not assume that the field is "reason"
merely because this is a cancellation request.

REPLACEMENT VALUE RULES:

Only after selecting edit_reason should you
determine whether a new reason was supplied.

A request to change the reason is NOT itself
a replacement reason.

If the customer asks to change the reason
but does not supply the replacement,
set new_reason to null.

Only extract an actual replacement value
from the current customer message.

Never use the editing instruction itself
as the replacement value.

When uncertain whether a replacement was
provided, use null rather than guessing.

"""



# -----------------------------------
# 3. Local extraction model
# -----------------------------------

extraction_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    CancellationEditExtraction,
    method="json_schema"
)


# -----------------------------------
# 4. Extraction function
# -----------------------------------


def extract_cancellation_edit(message: str):

    result = extraction_llm.invoke([
        ("system", CANCELLATION_EDIT_PROMPT),
        ("human", message)
    ])

    # A replacement reason is valid only for
    # an edit_reason action.
    if result.action != "edit_reason":
        result.new_reason = None
        return result

    # No replacement was supplied.
    if result.new_reason is None:
        return result

    proposed_reason = result.new_reason.strip()


# Reject cases where the LLM copies the entire
# editing instruction as the new reason.

    normalized_reason = " ".join(
        proposed_reason.casefold().strip(" .,!?\"'").split()
    )

    normalized_message = " ".join(
        message.casefold().strip(" .,!?\"'").split()
    )

    if normalized_reason == normalized_message:
        result.new_reason = None
        return result


    # Reject empty or invented values.
    if (
        not proposed_reason
        or proposed_reason.casefold() not in message.casefold()
    ):
        result.new_reason = None

    else:
        result.new_reason = proposed_reason

    return result



# -----------------------------------
# Follow-up reason extraction
# -----------------------------------

class ReasonFollowup(BaseModel):
    action: Literal[
        "provide_reason",
        "stop_editing",
        "unclear"
    ]

    new_reason: str | None = None


reason_followup_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    ReasonFollowup,
    method="json_schema"
)


REASON_FOLLOWUP_PROMPT = """
You interpret the customer's reply in an
unfinished cancellation-reason editing workflow.

CONTEXT:
The customer has an unsubmitted cancellation draft.
The assistant has specifically asked the customer
to supply a NEW cancellation reason.

Classify the latest reply:

provide_reason:
The customer actually supplies a replacement reason.
The replacement may be just a short phrase or sentence.
Extract only the reason text into new_reason.

stop_editing:
The customer explicitly wants to stop EDITING the
reason and keep the original cancellation draft.

unclear:
The customer asks a question, gives no usable reason,
asks to submit, or appears to want to cancel the
entire draft rather than just the edit.

Rules:
- Never invent a reason.
- Copy the reason faithfully from the current message.
- Do not extract anything from these instructions.
- Do not treat "yes", "no", or "go ahead" as reasons.
- If a short message might be either a cancellation
  instruction or a reason, prefer unclear.
- Never submit or discard a request.
- Return only structured output.
"""


def extract_reason_followup(message: str) -> ReasonFollowup:

    result = reason_followup_llm.invoke([
        ("system", REASON_FOLLOWUP_PROMPT),
        ("human", message)
    ])

    # No valid replacement was extracted
    if (
        result.action != "provide_reason"
        or not result.new_reason
    ):
        if result.action == "provide_reason":
            result.action = "unclear"

        result.new_reason = None
        return result

    new_reason = result.new_reason.strip()

    # Python safeguard against invented values
    if (
        not new_reason
        or new_reason.casefold() not in message.casefold()
    ):
        result.action = "unclear"
        result.new_reason = None
    else:
        result.new_reason = new_reason

    return result


