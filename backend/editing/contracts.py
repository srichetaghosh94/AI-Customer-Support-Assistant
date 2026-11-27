
from typing import Literal

from pydantic import BaseModel, Field


# ----------------------------------------
# 1. Supported draft types
# ----------------------------------------

DraftType = Literal[
    "cancellation",
    "refund",
    "ticket"
]


# ----------------------------------------
# 2. Fields the AI can identify
# ----------------------------------------

EditField = Literal[
    "reason",
    "order_id",
    "amount",
    "subject",
    "description",
    "customer_id",
    "unknown"
]


# ----------------------------------------
# 3. Supported editing operations
# ----------------------------------------

EditOperation = Literal[
    "replace",
    "append",
    "full_refund",
    "unlink",
    "unknown"
]


# ----------------------------------------
# 4. Structured output for the AI extractor
# ----------------------------------------


class EditExtraction(BaseModel):

    field: EditField

    operation: EditOperation

    value_provided: bool = Field(
        description=(
            "True only when the customer actually "
            "supplies replacement or additional content. "
            "False when the customer only asks to edit."
        )
    )

    new_value: str | None = Field(
        default=None,
        description=(
            "The exact new content supplied by the customer. "
            "Exclude editing instructions. "
            "Use JSON null if no new content was supplied."
        )
    )



# ----------------------------------------
# 5. State for an unfinished edit
# ----------------------------------------

class PendingEdit(BaseModel):

    draft_type: DraftType

    field: EditField

    operation: EditOperation


# ----------------------------------------
# 6. Allowed edits for each request type
# ----------------------------------------

ALLOWED_EDITS = {

    "cancellation": {

        "reason": {"replace"},

        "order_id": {"replace"}
    },

    "refund": {

        "reason": {"replace"},

        "amount": {
            "replace",
            "full_refund"
        },

        "order_id": {"replace"}
    },

    "ticket": {

        "subject": {"replace"},

        "description": {
            "replace",
            "append"
        },

        "order_id": {
            "replace",
            "unlink"
        }
    }
}


# ----------------------------------------
# 7. Check if an edit is supported
# ----------------------------------------

def is_edit_allowed(
    draft_type: str,
    field: str,
    operation: str
) -> bool:

    allowed_fields = ALLOWED_EDITS.get(
        draft_type,
        {}
    )

    allowed_operations = allowed_fields.get(
        field,
        set()
    )

    return operation in allowed_operations
