
import json
from typing import Literal

from pydantic import BaseModel
from langchain_ollama import ChatOllama

from editing.contracts import is_edit_allowed


class EditFollowup(BaseModel):

    decision: Literal[
        "provide_value",
        "stop_editing",
        "unclear"
    ]

    new_value: str | None = None


followup_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    EditFollowup,
    method="json_schema"
)


FOLLOWUP_PROMPT = """
You interpret a customer's reply in an
UNFINISHED draft-editing conversation.

The assistant has ALREADY asked the customer
to provide a new value for a specific field.

Trusted context includes:
- draft_type
- field
- operation

Your job is to interpret the latest reply.

DECISIONS:

provide_value:
The customer supplies actual replacement
or additional content for the field
currently being edited.

A standalone answer can be the entire
customer message.

For example, if asked for a new reason:
"Ordered twice"
is a valid replacement value.

If asked for a new refund amount:
"25.50"
is a valid replacement value.

If asked for a ticket description:
"The package arrived damaged"
is valid content.

Extract only the supplied value.
Do not invent or paraphrase anything.

stop_editing:
The customer explicitly wants to abandon
the CURRENT EDIT and keep the original draft.

This does NOT mean discarding the entire
cancellation, refund, or ticket request.

unclear:
The reply does not supply a usable value
for the currently selected field.

This includes:
- Questions unrelated to supplying the value.
- Requests to edit a different field.
- Ambiguous replies.
- Confirmation messages such as "yes",
  "go ahead", or "submit it".
- Requests to discard the entire draft.

IMPORTANT SAFETY RULES:

Never interpret confirmation as a new value.

Never submit a request.
Never discard the entire draft.
Never update any draft.

If the customer explicitly wants to
stop the current edit, choose stop_editing.

If their intention is ambiguous,
choose unclear.

If decision is not provide_value,
new_value must be JSON null.

Use actual JSON null, not the string "null".

Return only structured output.
"""


def extract_edit_followup(
    message: str,
    draft_type: str,
    field: str,
    operation: str
) -> EditFollowup:

    if not message.strip():
        raise ValueError(
            "Customer message cannot be empty"
        )

    if not is_edit_allowed(
        draft_type,
        field,
        operation
    ):
        raise ValueError(
            "Unsupported pending edit"
        )

    # These operations don't need a
    # replacement-value follow-up.
    if operation not in ("replace", "append"):
        raise ValueError(
            "This operation does not require a value"
        )

    context = {
        "draft_type": draft_type,
        "field": field,
        "operation": operation,
        "customer_message": message
    }

    result = followup_llm.invoke([
        ("system", FOLLOWUP_PROMPT),
        (
            "human",
            json.dumps(
                context,
                ensure_ascii=False
            )
        )
    ])

    if not isinstance(result, EditFollowup):
        raise ValueError(
            "Invalid follow-up extraction"
        )

    # No value should be returned when
    # the customer didn't provide one.
    if result.decision != "provide_value":

        result.new_value = None

        return result

    value = (result.new_value or "").strip()

    if (
        not value
        or value.casefold() in ("null", "none")
        or value.casefold() not in message.casefold()
    ):
        return EditFollowup(
            decision="unclear",
            new_value=None
        )

    # Do NOT reject a value just because
    # it equals the entire customer message.
    #
    # In a follow-up, "Ordered twice"
    # can be the complete replacement reason.

    return EditFollowup(
        decision="provide_value",
        new_value=value
    )
