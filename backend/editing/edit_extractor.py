
import json

from pydantic import BaseModel
from langchain_ollama import ChatOllama

from editing.contracts import (
    DraftType,
    EditField,
    EditOperation,
    EditExtraction,
    is_edit_allowed
)

from editing.value_extractor import extract_edit_value


# -------------------------------------
# 1. Field and operation identification
# -------------------------------------

class EditTarget(BaseModel):
    field: EditField
    operation: EditOperation


target_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    EditTarget,
    method="json_schema"
)


# -------------------------------------
# 2. Universal identification prompt
# -------------------------------------

EDIT_TARGET_PROMPT = """
You identify what a customer wants to edit
in an UNSUBMITTED customer support draft.

The backend provides the draft_type:
cancellation, refund, or ticket.

Your ONLY job is to identify:

1. FIELD
2. OPERATION

Do NOT extract replacement values.
Do NOT decide whether to submit anything.
Do NOT change the draft.

SUPPORTED FIELDS:

Cancellation:
- reason
- order_id

Refund:
- reason
- amount
- order_id

Ticket:
- subject
- description
- order_id

If the customer explicitly asks to change
their customer ID:
field=customer_id
operation=replace

The backend will reject this edit.

If the field is not identifiable:
field=unknown
operation=unknown

FIELD RULES:

A cancellation request is not the same thing
as a cancellation reason.

Do not assume a customer means the reason
just because they mention editing a
cancellation request.

Identify a field only when it is explicitly
mentioned or unambiguously implied.

For support tickets:

subject:
The ticket title or heading.

description:
The customer's explanation, issue details,
additional information, and context.

When a customer wants to add more details
to a ticket without specifying another
field, choose description.

OPERATION RULES:

replace:
The customer wants to change, correct,
rewrite, or replace an existing field.

Rewriting a ticket description means
replace, not append.

append:
The customer wants to add information
without removing existing information.

Adding more details to a support ticket
usually means:
field=description
operation=append

full_refund:
The customer wants the complete eligible
refund rather than a partial refund.

For refund requests:
field=amount
operation=full_refund

The customer does not need to say "amount".

unlink:
The customer wants to REMOVE the order
association from a support ticket.

Only use unlink when they actually want
the association removed.

Linking another order, correcting an order,
or switching to a different order means:
field=order_id
operation=replace

unknown:
Use when the intended editing operation
cannot be identified.

IMPORTANT:

Do not guess a field when the customer
only says they want to change something.

Do not extract new values.
That is handled by a separate stage.

Return only structured output.
"""


# -------------------------------------
# 3. Unified edit interpreter
# -------------------------------------

def extract_edit_request(
    message: str,
    draft_type: DraftType
) -> EditExtraction:

    if not message.strip():
        raise ValueError(
            "Customer message cannot be empty"
        )

    if draft_type not in (
        "cancellation",
        "refund",
        "ticket"
    ):
        raise ValueError(
            "Unsupported draft type"
        )

    # ---------------------------------
    # STAGE 1:
    # Identify field and operation
    # ---------------------------------

    context = {
        "draft_type": draft_type,
        "customer_message": message
    }

    target = target_llm.invoke([
        (
            "system",
            EDIT_TARGET_PROMPT
        ),
        (
            "human",
            json.dumps(
                context,
                ensure_ascii=False
            )
        )
    ])

    if not isinstance(target, EditTarget):
        raise ValueError(
            "Invalid edit target extraction"
        )

    # Unknown or unsupported edits must not
    # proceed to replacement-value extraction.

    if not is_edit_allowed(
        draft_type,
        target.field,
        target.operation
    ):
        return EditExtraction(
            field=target.field,
            operation=target.operation,
            value_provided=False,
            new_value=None
        )

    # ---------------------------------
    # STAGE 2:
    # Extract replacement content
    # ---------------------------------

    value_result = extract_edit_value(
        message=message,
        draft_type=draft_type,
        field=target.field,
        operation=target.operation
    )

    # ---------------------------------
    # Return one unified result
    # ---------------------------------

    return EditExtraction(
        field=target.field,
        operation=target.operation,
        value_provided=value_result.value_provided,
        new_value=value_result.new_value
    )
