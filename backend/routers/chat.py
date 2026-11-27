"""Unified draft editing for the local FastAPI customer-support chatbot.

Replace backend/routers/chat.py with this file.
Requires the previously built editing/* modules and response_generator.py.
"""

import json
from threading import Lock
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import agent
from confirmation_prompt import CONFIRMATION_SYSTEM_PROMPT
from modification_classifier import detect_modification
from response_generator import generate_customer_reply
from editing.contracts import EditExtraction, is_edit_allowed
from editing.edit_extractor import extract_edit_request
from editing.followup_extractor import extract_edit_followup
from editing.draft_editor import (
    apply_text_edit,
    apply_refund_amount_edit,
    apply_order_id_edit,
)

router = APIRouter(prefix="/chat", tags=["Chat"])
API_BASE = "http://127.0.0.1:8000"
submission_lock = Lock()  # In-process protection for this local demo.

DRAFT_KEYS = {
    "cancellation": "pending_cancellation",
    "refund": "pending_refund",
    "ticket": "pending_ticket",
}
SUBMISSION_PATHS = {
    "cancellation": "/cancellations",
    "refund": "/refunds",
    "ticket": "/tickets",
}
PREPARATION_TO_TYPE = {
    "prepare_cancellation_request": "cancellation",
    "prepare_refund_request": "refund",
    "prepare_support_ticket": "ticket",
}


class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str


class ConfirmationIntent(BaseModel):
    decision: Literal["confirm", "cancel", "unclear"]


confirmation_llm = ChatOllama(
    model="qwen3:4b", temperature=0, reasoning=False
).with_structured_output(ConfirmationIntent, method="json_schema")


def _state(config: dict) -> dict:
    return agent.get_state(config).values or {}


def save_chat_response(config: dict, user_message: str, reply: str, **updates):
    agent.update_state(config, {
        **updates,
        "messages": [HumanMessage(content=user_message), AIMessage(content=reply)],
    })


def _assert_current(
    config: dict, draft_type: str, old_draft: dict, old_pending_edit
):
    current = _state(config)
    if (
        current.get(DRAFT_KEYS[draft_type]) != old_draft
        or current.get("pending_edit") != old_pending_edit
    ):
        raise HTTPException(
            status_code=409,
            detail="The draft changed while this message was being processed. Please try again.",
        )


def _draft_preview(draft_type: str, draft: dict) -> str:
    """Exact saved values, never re-created by the model."""
    lines = ["Draft for review:", f"Customer ID: {draft.get('customer_id')}"]
    if draft_type == "ticket":
        lines.extend([
            f"Order ID: {draft.get('order_id') or 'Not linked'}",
            f"Subject: {draft.get('subject')}",
            f"Description: {draft.get('description')}",
        ])
    elif draft_type == "refund":
        lines.extend([
            f"Order ID: {draft.get('order_id')}",
            f"Reason: {draft.get('reason')}",
            f"Amount: {draft.get('amount') if draft.get('amount') is not None else 'NOT SELECTED'}",
        ])
    else:
        lines.extend([
            f"Order ID: {draft.get('order_id')}",
            f"Reason: {draft.get('reason') or 'Not provided'}",
        ])
    lines.append("Submission status: NOT SUBMITTED")
    return "\n".join(lines)


def _natural_reply(
    config: dict,
    message: str,
    outcome: str,
    draft_type: str,
    draft: dict,
    *,
    details: dict | None = None,
    new_draft: dict | None = None,
    new_pending_edit=None,
    update_state: bool = False,
    old_pending_edit=None,
    show_preview: bool = False,
) -> dict:
    target = new_draft if new_draft is not None else draft
    reply = generate_customer_reply(
        customer_message=message,
        outcome=outcome,
        draft=target,
        details={"submitted": False, **(details or {})},
    )
    if show_preview:
        reply += "\n\n" + _draft_preview(draft_type, target)

    if update_state:
        with submission_lock:
            _assert_current(config, draft_type, draft, old_pending_edit)
            save_chat_response(
                config,
                message,
                reply,
                **{
                    DRAFT_KEYS[draft_type]: target,
                    "pending_edit": new_pending_edit,
                },
            )
    else:
        save_chat_response(config, message, reply)
    return {"reply": reply}


def _verified_order(order_id: str) -> dict:
    """Fetch order data from FastAPI; never trust model-generated order facts."""
    try:
        valid_id = str(UUID(str(order_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("The order ID must be a valid UUID.") from exc

    try:
        response = httpx.get(f"{API_BASE}/orders/{valid_id}", timeout=15.0)
    except httpx.RequestError as exc:
        raise HTTPException(503, "Order verification service is unavailable.") from exc

    if response.status_code == 404:
        raise ValueError("That order ID was not found.")
    if response.status_code != 200:
        raise HTTPException(503, "Could not verify the order with the backend.")
    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(502, "Invalid order verification response.") from exc
    if not isinstance(data, dict):
        raise HTTPException(502, "Invalid order verification response.")
    return data


def _pending_context(draft_type: str, field: str, operation: str) -> dict:
    return {"draft_type": draft_type, "field": field, "operation": operation}


def _handle_edit(
    config: dict,
    message: str,
    draft_type: str,
    draft: dict,
    *,
    field: str,
    operation: str,
    value: str | None,
    value_provided: bool,
    old_pending_edit=None,
) -> dict:
    if not is_edit_allowed(draft_type, field, operation):
        return _natural_reply(
            config, message, "edit_not_supported", draft_type, draft,
            details={
                "field": field,
                "operation": operation,
                "draft_unchanged": True,
                "next_step": "Explain what cannot be edited and ask for an allowed field.",
            },
        )

    # The customer has asked for an edit but hasn't provided the new value.
    if operation in ("replace", "append") and (not value_provided or not value):
        return _natural_reply(
            config, message, "awaiting_edit_value", draft_type, draft,
            details={
                "field": field, "operation": operation,
                "draft_unchanged": True,
                "next_step": "Ask for the new value; do not request submission yet.",
            },
            new_pending_edit=_pending_context(draft_type, field, operation),
            update_state=True,
            old_pending_edit=old_pending_edit,
        )

    edit = EditExtraction(
        field=field,
        operation=operation,
        value_provided=value_provided,
        new_value=value,
    )
    try:
        if field == "order_id":
            order = None
            if operation == "replace":
                order = _verified_order(value or "")
            updated = apply_order_id_edit(draft_type, draft, edit, order)
        elif field == "amount":
            order = _verified_order(str(draft.get("order_id", "")))
            updated = apply_refund_amount_edit(draft, edit, order)
        else:
            updated = apply_text_edit(draft_type, draft, edit)
    except ValueError as exc:
        # Invalid edits do not overwrite the original draft.
        retry_edit = (
            _pending_context(draft_type, field, operation)
            if operation in ("replace", "append")
            else None
        )
        return _natural_reply(
            config, message, "edit_validation_failed", draft_type, draft,
            details={
                "validation_error": str(exc),
                "draft_unchanged": True,
                "next_step": "Explain why the change was rejected and ask for a corrected value.",
            },
            new_pending_edit=retry_edit,
            update_state=True,
            old_pending_edit=old_pending_edit,
        )

    # A refund amount is tied to its order. After switching orders, it must
    # be re-entered or recalculated before any submission is permitted.
    needs_amount = draft_type == "refund" and updated.get("amount") is None
    next_edit = (
        _pending_context("refund", "amount", "replace")
        if needs_amount else None
    )
    return _natural_reply(
        config,
        message,
        "draft_updated_amount_required" if needs_amount else "draft_updated_requires_submission_confirmation",
        draft_type,
        draft,
        details={
            "updated_field": field,
            "operation": operation,
            "draft_changed": updated != draft,
            "next_step": (
                "Ask the customer for a new refund amount or a full refund choice. "
                "Do not submit or ask for submission confirmation yet."
                if needs_amount else
                "Explain the edit and ask whether to SUBMIT the updated request. "
                "Submission still requires a fresh customer confirmation."
            ),
        },
        new_draft=updated,
        new_pending_edit=next_edit,
        update_state=True,
        old_pending_edit=old_pending_edit,
        show_preview=True,
    )


def _confirmation_decision(message: str) -> str:
    intent = confirmation_llm.invoke([
        ("system", CONFIRMATION_SYSTEM_PROMPT),
        ("human", message),
    ])
    print("CONFIRMATION INTENT:", intent.decision, flush=True)
    return intent.decision


def _handle_pending_edit(
    config: dict,
    message: str,
    draft_type: str,
    draft: dict,
    pending_edit: dict,
) -> dict:
    if pending_edit.get("draft_type") != draft_type:
        raise HTTPException(409, "Pending edit does not match the active draft.")
    field, operation = pending_edit.get("field"), pending_edit.get("operation")
    if not is_edit_allowed(draft_type, field, operation):
        raise HTTPException(409, "Invalid pending edit.")

    # A mistaken stop_editing classification must not silently abandon an edit.
    # Ask for a separate confirmation about stopping the edit only.
    if pending_edit.get("confirm_stop"):
        decision = _confirmation_decision(message)
        if decision == "confirm":
            return _natural_reply(
                config, message, "edit_abandoned_original_draft_preserved",
                draft_type, draft,
                details={"draft_unchanged": True, "next_step": "Ask whether to submit, edit again, or discard the original draft."},
                new_pending_edit=None, update_state=True,
                old_pending_edit=pending_edit,
            )
        if decision == "cancel":
            return _natural_reply(
                config, message, "continue_waiting_for_edit_value",
                draft_type, draft,
                details={"field": field, "next_step": "Ask for the replacement value."},
                new_pending_edit=_pending_context(draft_type, field, operation),
                update_state=True, old_pending_edit=pending_edit,
            )
        return _natural_reply(
            config, message, "clarify_whether_to_stop_editing",
            draft_type, draft,
            details={"draft_unchanged": True, "next_step": "Ask whether the customer wants to stop editing but keep their draft."},
        )

    # A clearly requested edit takes priority over submission intent. This
    # also supports switching fields while a previous edit is incomplete.
    modification = detect_modification(message)
    print("MODIFICATION INTENT:", modification, flush=True)
    if modification == "modify":
        edit = extract_edit_request(message, draft_type)
        if edit.field != "unknown" and is_edit_allowed(draft_type, edit.field, edit.operation):
            return _handle_edit(
                config, message, draft_type, draft,
                field=edit.field, operation=edit.operation,
                value=edit.new_value, value_provided=edit.value_provided,
                old_pending_edit=pending_edit,
            )
        return _natural_reply(
            config, message, "edit_target_unclear_or_unsupported", draft_type, draft,
            details={"draft_unchanged": True, "next_step": "Ask the customer to clarify which field they want to edit."},
        )

    # During an incomplete edit, even an affirmative submission request must
    # NOT reach the POST submission branch. Our 8/10 experimental follow-up
    # classifier occasionally labeled confirmation as stop_editing.
    decision = _confirmation_decision(message)
    if decision == "confirm":
        return _natural_reply(
            config, message, "cannot_submit_while_edit_value_missing",
            draft_type, draft,
            details={
                "field": field,
                "draft_unchanged": True,
                "next_step": "Explain that the requested edit needs a value first. No submission occurred.",
            },
        )

    followup = extract_edit_followup(
        message, draft_type=draft_type, field=field, operation=operation
    )
    print("EDIT FOLLOWUP:", followup.decision, repr(followup.new_value), flush=True)
    if followup.decision == "provide_value" and followup.new_value:
        return _handle_edit(
            config, message, draft_type, draft,
            field=field, operation=operation,
            value=followup.new_value, value_provided=True,
            old_pending_edit=pending_edit,
        )
    if followup.decision == "stop_editing":
        return _natural_reply(
            config, message, "confirm_stop_editing_only", draft_type, draft,
            details={
                "draft_unchanged": True,
                "next_step": "Ask whether the customer wants to abandon only the current edit and keep the original request draft. Do not submit or discard it.",
            },
            new_pending_edit={**_pending_context(draft_type, field, operation), "confirm_stop": True},
            update_state=True, old_pending_edit=pending_edit,
        )
    return _natural_reply(
        config, message, "still_waiting_for_edit_value", draft_type, draft,
        details={"field": field, "draft_unchanged": True, "next_step": "Ask for the replacement or added content, without submitting anything."},
    )


def _preflight(draft_type: str, draft: dict) -> None:
    """Revalidate current order data immediately before submitting a draft."""
    if draft_type == "refund" and draft.get("amount") is None:
        raise ValueError("A refund amount must be chosen before submitting.")

    order_id = draft.get("order_id")
    if not order_id:
        if draft_type in ("refund", "cancellation"):
            raise ValueError("An order ID is required for this request.")
        return  # A support ticket can have no linked order.

    order = _verified_order(str(order_id))
    apply_order_id_edit(
        draft_type,
        draft,
        EditExtraction(
            field="order_id", operation="replace",
            value_provided=True, new_value=str(order_id)
        ),
        order,
    )
    if draft_type == "refund":
        apply_refund_amount_edit(
            draft,
            EditExtraction(
                field="amount", operation="replace",
                value_provided=True, new_value=str(draft["amount"]),
            ),
            order,
        )


def _submit_draft(config: dict, message: str, draft_type: str, draft: dict) -> dict:
    with submission_lock:
        _assert_current(config, draft_type, draft, None)
        try:
            _preflight(draft_type, draft)
        except ValueError as exc:
            # A validation failure must not reach the POST endpoint.
            raise HTTPException(422, str(exc)) from exc

        try:
            response = httpx.post(
                f"{API_BASE}{SUBMISSION_PATHS[draft_type]}",
                json=draft,
                timeout=15.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                503,
                "Submission result is unknown. Check request records before retrying.",
            ) from exc

        if response.status_code != 201:
            try:
                payload = response.json()
                detail = payload.get("detail", "Request not submitted") if isinstance(payload, dict) else "Request not submitted"
            except ValueError:
                detail = "Request not submitted"
            raise HTTPException(response.status_code, detail)

        # A 201 means the backend accepted the creation. Even if its receipt
        # is malformed, clear the draft rather than invite a duplicate POST.
        try:
            created = response.json()
        except ValueError:
            created = {}
        if not isinstance(created, dict):
            created = {}

        id_field = {
            "ticket": "ticket_id",
            "refund": "refund_id",
            "cancellation": "cancellation_id",
        }[draft_type]
        receipt_id = created.get(id_field)
        status = created.get("status")
        if not receipt_id:
            reply = (
                "The backend accepted your request (HTTP 201), but no receipt ID "
                "was returned. Check the saved requests before trying again."
            )
        elif draft_type == "ticket":
            reply = f"Your support ticket was created. Ticket ID: {receipt_id}. Status: {status or 'created'}."
        elif draft_type == "refund":
            reply = f"Your refund request was submitted. Refund ID: {receipt_id}. Status: {status or 'pending'}."
        else:
            reply = (
                f"Your cancellation request was submitted. Cancellation ID: {receipt_id}. "
                f"Status: {status or 'pending'}. Your order has not been cancelled yet; approval is still required."
            )

        # Do not call the LLM between the successful POST and clearing the draft.
        save_chat_response(
            config, message, reply,
            **{DRAFT_KEYS[draft_type]: None, "pending_edit": None},
        )
        return {"reply": reply}


def _new_draft_from_tools(config: dict, message: str, previous_count: int, result: dict) -> dict:
    last_message = result["messages"][-1]
    reply = last_message.content
    if not isinstance(reply, str):
        raise HTTPException(502, "The AI produced an invalid response.")
    if "</think>" in reply:
        reply = reply.rsplit("</think>", 1)[-1].strip()
    if "<think>" in reply or not reply:
        raise HTTPException(502, "The AI did not produce a clean answer.")

    new_messages = result["messages"][previous_count:]
    prepared = []
    for item in new_messages:
        if not isinstance(item, ToolMessage):
            continue
        draft_type = PREPARATION_TO_TYPE.get(item.name)
        if not draft_type:
            continue
        try:
            data = json.loads(item.content)
        except (ValueError, TypeError):
            continue
        if data.get("confirmation_required") and isinstance(data.get("draft"), dict):
            prepared.append((draft_type, data["draft"]))

    if len(prepared) > 1:
        reply = "Multiple requests were prepared. Please choose which request to handle first. Nothing was submitted."
    elif len(prepared) == 1:
        draft_type, draft = prepared[0]
        reply = (
            f"I've prepared your {draft_type} request.\n\n"
            + _draft_preview(draft_type, draft)
            + "\n\nWould you like to submit this request?"
            + (" It will require admin approval." if draft_type == "cancellation" else "")
        )
        agent.update_state(config, {DRAFT_KEYS[draft_type]: draft})

    if len(prepared) != 0:
        # Replace the final AI message, as in the existing working V3 router.
        agent.update_state(config, {
            "messages": [AIMessage(id=last_message.id, content=reply)]
        })
    return {"reply": reply}


@router.post("", response_model=ChatResponse)
def chatbot(request: ChatRequest):
    config = {
        "configurable": {"thread_id": str(request.conversation_id)},
        "recursion_limit": 8,
    }
    message = request.message
    try:
        state = _state(config)
        active = [
            (name, state[key])
            for name, key in DRAFT_KEYS.items()
            if state.get(key)
        ]
        if len(active) > 1:
            raise HTTPException(409, "Multiple pending request drafts were found.")

        if active:
            draft_type, draft = active[0]
            pending_edit = state.get("pending_edit")

            if pending_edit is not None:
                if not isinstance(pending_edit, dict):
                    raise HTTPException(409, "Old editing state detected; start a fresh conversation after restarting the backend.")
                return _handle_pending_edit(config, message, draft_type, draft, pending_edit)

            modification = detect_modification(message)
            print("MODIFICATION INTENT:", modification, flush=True)
            if modification == "uncertain":
                return _natural_reply(
                    config, message, "uncertain_customer_intent", draft_type, draft,
                    details={"draft_unchanged": True, "next_step": "Ask whether to edit, submit, or discard the request."},
                )
            if modification == "modify":
                edit = extract_edit_request(message, draft_type)
                print("UNIFIED EDIT:", edit, flush=True)
                return _handle_edit(
                    config, message, draft_type, draft,
                    field=edit.field, operation=edit.operation,
                    value=edit.new_value, value_provided=edit.value_provided,
                    old_pending_edit=None,
                )
            if modification != "not_modify":
                raise HTTPException(503, "Unexpected modification decision.")

            decision = _confirmation_decision(message)
            if decision == "confirm":
                return _submit_draft(config, message, draft_type, draft)
            if decision == "cancel":
                with submission_lock:
                    _assert_current(config, draft_type, draft, None)
                    reply = "Your draft was discarded. Nothing was submitted."
                    save_chat_response(config, message, reply, **{
                        DRAFT_KEYS[draft_type]: None, "pending_edit": None,
                    })
                return {"reply": reply}
            return _natural_reply(
                config, message, "awaiting_submission_decision", draft_type, draft,
                details={"draft_unchanged": True, "next_step": "Ask for clarification about submission or draft editing."},
            )

        if state.get("pending_edit") is not None:
            raise HTTPException(409, "An unfinished edit exists without a draft.")
        previous_count = len(state.get("messages", []))
        result = agent.invoke(
            {"messages": [HumanMessage(content=message)]}, config=config
        )
        return _new_draft_from_tools(config, message, previous_count, result)

    except HTTPException:
        raise
    except Exception as exc:
        print("CHAT ERROR:", repr(exc), flush=True)
        raise HTTPException(503, "Could not process the chat message.") from exc
