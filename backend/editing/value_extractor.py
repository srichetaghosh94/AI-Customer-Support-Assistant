
import json

from pydantic import BaseModel
from langchain_ollama import ChatOllama


class ValueExtraction(BaseModel):
    value_provided: bool
    new_value: str | None = None


value_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    ValueExtraction,
    method="json_schema"
)



VALUE_EXTRACTION_PROMPT = """
You are a precise information extraction system.

A customer wants to edit an UNSUBMITTED
customer support request.

The backend has ALREADY identified:
- draft_type
- field
- operation

These are trusted inputs.

Your ONLY job is to extract the new value
from the customer's latest message.

IMPORTANT:

Customers can provide new information
using natural instructions.

For example, messages of the form:

- Change [field] to [new content]
- Set [field] to [new content]
- Replace [field] with [new content]
- Rewrite [field] as [new content]
- Add [new content] to [field]

contain actual new values.

Extract the CONTENT, not the instruction.

Do not mistake the instruction words
for the new value.

Do not return false simply because
the customer used an editing command.

DECISION RULES:

1. If the message contains concrete new
   information for the specified field,
   return:
   value_provided=true
   new_value=the exact supplied information

2. If the customer only requests permission
   to edit or says they want to edit,
   without supplying new information,
   return:
   value_provided=false
   new_value=null

3. For operation=append:
   Extract ONLY the additional content.
   Do not include the instruction to add it.

4. For operation=replace:
   Extract ONLY the replacement content.
   Do not include the instruction to replace it.

5. For field=amount:
   Extract the exact numeric amount supplied.
   Do not calculate or invent an amount.

6. For field=order_id:
   Extract the exact identifier supplied.
   Do not invent an identifier.

7. If no concrete new value exists:
   Return JSON null, NOT the string "null".

8. Preserve the original wording.
   Do not paraphrase, improve, or summarize.

EXAMPLES:

Input context:
field=reason
operation=replace
message="Change my reason to Bought the wrong color"

Output:
value_provided=true
new_value="Bought the wrong color"

Input context:
field=reason
operation=replace
message="I would like to change my reason first"

Output:
value_provided=false
new_value=null

Input context:
field=description
operation=append
message="Please add Screen flickers to my description"

Output:
value_provided=true
new_value="Screen flickers"

Input context:
field=description
operation=append
message="I have more details to add"

Output:
value_provided=false
new_value=null

Input context:
field=description
operation=replace
message="Rewrite the description as Box arrived dented"

Output:
value_provided=true
new_value="Box arrived dented"

Input context:
field=description
operation=replace
message="Can I rewrite the description?"

Output:
value_provided=false
new_value=null

Input context:
field=subject
operation=replace
message="Change the subject to Delivery issue"

Output:
value_provided=true
new_value="Delivery issue"

IMPORTANT FINAL CHECK:

Ask yourself:

"Did the customer provide actual content
that can be placed into this field?"

If yes, extract that content.

If no, return null.

Return only structured output.
"""



def extract_edit_value(
    message: str,
    draft_type: str,
    field: str,
    operation: str
) -> ValueExtraction:

    if not message.strip():
        raise ValueError("Empty customer message")

    # These operations don't require text values.
    if operation in ("full_refund", "unlink"):
        return ValueExtraction(
            value_provided=False,
            new_value=None
        )

    if operation not in ("replace", "append"):
        raise ValueError("Unsupported value operation")

    context = {
        "draft_type": draft_type,
        "field": field,
        "operation": operation,
        "customer_message": message
    }

    result = value_llm.invoke([
        ("system", VALUE_EXTRACTION_PROMPT),
        (
            "human",
            json.dumps(context, ensure_ascii=False)
        )
    ])

    print(
        "\nRAW VALUE EXTRACTION:",
        repr(result),
        flush=True
    )

    if not isinstance(result, ValueExtraction):
        raise ValueError("Invalid value extraction")

    if not result.value_provided or not result.new_value:
        return ValueExtraction(
            value_provided=False,
            new_value=None
        )

    value = result.new_value.strip()

    if (
        not value
        or value.casefold() in ("null", "none")
        or value.casefold() not in message.casefold()
    ):
        return ValueExtraction(
            value_provided=False,
            new_value=None
        )

    # Reject a copied entire instruction.
    normalized_value = " ".join(
        value.casefold().strip(" .,!?\"'").split()
    )

    normalized_message = " ".join(
        message.casefold().strip(" .,!?\"'").split()
    )

    if normalized_value == normalized_message:
        return ValueExtraction(
            value_provided=False,
            new_value=None
        )

    return ValueExtraction(
        value_provided=True,
        new_value=value
    )
