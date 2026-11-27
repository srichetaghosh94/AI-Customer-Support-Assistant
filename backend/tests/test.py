
from response_generator import generate_customer_reply

print("Starting response generator test...", flush=True)

try:
    reply = generate_customer_reply(
        customer_message="Can I change the cancellation reason?",
        outcome="awaiting_replacement_reason",
        draft={
            "reason": "I don't like it anymore"
        },
        details={
            "draft_submitted": False,
            "draft_changed": False,
            "next_step": "Ask the customer for their new cancellation reason"
        }
    )

    print("\nLLM RESPONSE:")
    print(reply)

except Exception as exc:
    print("\nERROR:", repr(exc))
