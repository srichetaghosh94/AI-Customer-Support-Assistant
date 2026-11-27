
from typing import Literal

from pydantic import BaseModel
from langchain_ollama import ChatOllama


# -----------------------------------
# 1. Modification intent schema
# -----------------------------------

class ModificationIntent(BaseModel):

    decision: Literal[
        "modify",
        "not_modify",
        "uncertain"
    ]


# -----------------------------------
# 2. Modification classifier prompt
# -----------------------------------

MODIFICATION_SYSTEM_PROMPT = """
You are a draft-modification intent detector
for an AI customer support assistant.

CONTEXT:

The customer has already prepared a request,
such as:
- A support ticket
- A refund request
- An order cancellation request

The request has NOT been submitted yet.

The customer is now responding to the assistant.

YOUR ONLY TASK:

Determine whether the customer wants to EDIT
information in the pending request.

Return exactly one decision:

1. modify

The customer clearly wants to edit, update,
correct, replace, or change a detail of the
existing draft.

This includes:
- Changing a refund amount
- Editing the cancellation reason
- Correcting an order ID
- Changing a support ticket description
- Asking whether they can modify a field

A request to modify remains a modification
even if the customer also says yes or no.

If the customer wants a change before submission,
classify as modify.

2. not_modify

The customer is clearly NOT requesting
a draft modification.

Examples of intentions:
- Approving submission
- Rejecting submission
- Asking an unrelated question
- Asking about the submission process
- Asking to review the draft without editing it

A customer rejecting the entire draft is
NOT requesting a modification.

3. uncertain

It is unclear whether the customer
wants to modify the draft.

Choose uncertain when the message
does not clearly establish whether an edit
is being requested.

IMPORTANT DISTINCTIONS:

- Changing the REASON for a cancellation
  is modifying the draft.

- Cancelling the entire REQUEST is
  not modifying the draft.

- A phrase like "I changed my mind" can
  be either a reason supplied as replacement
  text or a statement withdrawing a request.
  Interpret the whole sentence in context.

- Recognize minor spelling mistakes.

- Do not decide whether to submit or cancel.
  That belongs to another classifier.

- Do not extract replacement values yet.

- Return only the structured decision.
"""


# -----------------------------------
# 3. Local LLM
# -----------------------------------

modification_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    ModificationIntent,
    method="json_schema"
)


# -----------------------------------
# 4. Classifier function
# -----------------------------------

def detect_modification(message: str) -> str:

    result = modification_llm.invoke([
        (
            "system",
            MODIFICATION_SYSTEM_PROMPT
        ),
        (
            "human",
            message
        )
    ])

    return result.decision
