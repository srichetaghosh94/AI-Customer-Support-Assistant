
import json
from uuid import UUID
from threading import Lock
from typing import Literal

import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage
)

from agent import agent
from confirmation_prompt import CONFIRMATION_SYSTEM_PROMPT

from modification_classifier import detect_modification

from cancellation_edit_extractor import (
    extract_cancellation_edit,
    extract_reason_followup
)

from response_generator import generate_customer_reply


# -----------------------------------
# 1. FastAPI router
# -----------------------------------

router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


# -----------------------------------
# 2. Request and response models
# -----------------------------------

class ChatRequest(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str


# -----------------------------------
# 3. Confirmation classifier
# -----------------------------------

class ConfirmationIntent(BaseModel):
    decision: Literal[
        "confirm",
        "cancel",
        "unclear"
    ]


confirmation_llm = ChatOllama(
    model="qwen3:4b",
    temperature=0,
    reasoning=False
).with_structured_output(
    ConfirmationIntent,
    method="json_schema"
)


# Local-process lock for draft changes and submissions
submission_lock = Lock()


# -----------------------------------
# 4. Save conversation messages
# -----------------------------------

def save_chat_response(
    config: dict,
    user_message: str,
    reply: str,
    **state_updates
):

    agent.update_state(
        config,
        {
            **state_updates,
            "messages": [
                HumanMessage(content=user_message),
                AIMessage(content=reply)
            ]
        }
    )


# -----------------------------------
# 5. Generate natural workflow replies
# -----------------------------------

def send_workflow_reply(
    config: dict,
    user_message: str,
    outcome: str,
    draft: dict | None = None,
    details: dict | None = None,
    **state_updates
) -> dict:

    # Qwen3 generates customer-facing language
    reply = generate_customer_reply(
        customer_message=user_message,
        outcome=outcome,
        draft=draft,
        details=details
    )

    # Python saves the verified workflow state
    save_chat_response(
        config,
        user_message,
        reply,
        **state_updates
    )

    return {"reply": reply}


# -----------------------------------
# 6. Update cancellation reason draft
# -----------------------------------

def update_cancellation_reason(
    config: dict,
    user_message: str,
    new_reason: str
) -> dict:

    state = agent.get_state(config).values

    draft = state.get("pending_cancellation")

    if not isinstance(draft, dict):
        raise HTTPException(
            status_code=409,
            detail="No pending cancellation draft"
        )

    reason = new_reason.strip()

    # Never trust extracted LLM values blindly
    if (
        not reason
        or len(reason) > 500
        or reason.casefold() not in user_message.casefold()
    ):

        return send_workflow_reply(
            config,
            user_message,
            outcome="replacement_reason_invalid",
            draft=draft,
            details={
                "draft_changed": False,
                "draft_submitted": False,
                "next_step": (
                    "Ask for a valid replacement reason "
                    "of at most 500 characters"
                )
            },
            pending_edit="cancellation_reason"
        )

    # Update a COPY of the existing draft
    updated_draft = {
        **draft,
        "reason": reason
    }

    # Qwen3 generates the conversational reply
    reply = generate_customer_reply(
        customer_message=user_message,
        outcome="draft_updated_requires_fresh_confirmation",
        draft=updated_draft,
        details={
            "draft_changed": True,
            "draft_submitted": False,
            "updated_field": "reason",
            "updated_value": reason,
            "next_step": (
                "Tell the customer the reason has been updated. "
                "Ask for explicit confirmation before submission."
            )
        }
    )

    # Exact factual preview comes from Python,
    # rather than asking Qwen3 to reproduce IDs
    reply += (
        "\n\nDraft for review:\n"
        f"Customer ID: {updated_draft['customer_id']}\n"
        f"Order ID: {updated_draft['order_id']}\n"
        f"Reason: {updated_draft['reason']}\n"
        "Submission status: NOT SUBMITTED."
    )

    # Save under the local submission lock
    with submission_lock:

        latest_state = agent.get_state(config).values

        latest_draft = latest_state.get(
            "pending_cancellation"
        )

        if latest_draft != draft:
            raise HTTPException(
                status_code=409,
                detail="Cancellation draft changed during editing"
            )

        save_chat_response(
            config,
            user_message,
            reply,
            pending_cancellation=updated_draft,
            pending_edit=None
        )

    return {"reply": reply}


# -----------------------------------
# 7. POST /chat
# -----------------------------------

@router.post("", response_model=ChatResponse)
def chatbot(request: ChatRequest):

    config = {
        "configurable": {
            "thread_id": str(request.conversation_id)
        },
        "recursion_limit": 8
    }

    try:

        # -------------------------------------
        # A. Load LangGraph memory
        # -------------------------------------

        snapshot = agent.get_state(config)

        saved_state = snapshot.values if snapshot else {}

        pending_ticket = saved_state.get("pending_ticket")
        pending_refund = saved_state.get("pending_refund")
        pending_cancellation = saved_state.get(
            "pending_cancellation"
        )

        pending_edit = saved_state.get("pending_edit")

        # Only one draft may be pending at a time
        pending_count = sum(
            bool(draft)
            for draft in (
                pending_ticket,
                pending_refund,
                pending_cancellation
            )
        )

        if pending_count > 1:
            raise HTTPException(
                status_code=409,
                detail="Multiple pending requests exist"
            )

        # -------------------------------------
        # B. Handle pending request
        # -------------------------------------

        if (
            pending_ticket
            or pending_refund
            or pending_cancellation
        ):

            if pending_ticket:

                action_type = "ticket"
                state_key = "pending_ticket"
                endpoint = "http://127.0.0.1:8000/tickets"

            elif pending_refund:

                action_type = "refund"
                state_key = "pending_refund"
                endpoint = "http://127.0.0.1:8000/refunds"

            else:

                action_type = "cancellation"
                state_key = "pending_cancellation"
                endpoint = "http://127.0.0.1:8000/cancellations"

            draft = saved_state.get(state_key)

            # -------------------------------------
            # C. Already waiting for a new reason?
            # -------------------------------------

            if pending_edit is not None:

                if (
                    pending_edit != "cancellation_reason"
                    or not pending_cancellation
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Invalid draft editing state"
                    )

                try:
                    followup = extract_reason_followup(
                        request.message
                    )

                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail="Unable to interpret replacement reason"
                    ) from exc

                print(
                    "REASON FOLLOWUP:",
                    followup.action,
                    followup.new_reason,
                    flush=True
                )

                # Customer provided the new reason
                if (
                    followup.action == "provide_reason"
                    and followup.new_reason
                ):

                    return update_cancellation_reason(
                        config,
                        request.message,
                        followup.new_reason
                    )

                # Customer wants to stop editing
                if followup.action == "stop_editing":

                    return send_workflow_reply(
                        config,
                        request.message,
                        outcome="reason_edit_abandoned_draft_preserved",
                        draft=pending_cancellation,
                        details={
                            "draft_changed": False,
                            "draft_submitted": False,
                            "next_step": (
                                "Explain that the original reason "
                                "is unchanged and ask what "
                                "the customer wants next"
                            )
                        },
                        pending_edit=None
                    )

                # Unclear follow-up: preserve everything
                return send_workflow_reply(
                    config,
                    request.message,
                    outcome="still_awaiting_replacement_reason",
                    draft=pending_cancellation,
                    details={
                        "draft_changed": False,
                        "draft_submitted": False,
                        "next_step": (
                            "Ask for the replacement reason "
                            "or clarification"
                        )
                    }
                )

            # -------------------------------------
            # D. Detect modification intent first
            # -------------------------------------

            try:

                modification_decision = detect_modification(
                    request.message
                )

            except Exception as exc:

                raise HTTPException(
                    status_code=503,
                    detail="Unable to interpret modification intent"
                ) from exc

            print(
                "MODIFICATION INTENT:",
                modification_decision,
                flush=True
            )

            # -------------------------------------
            # E. Uncertain modification intent
            # -------------------------------------

            if modification_decision == "uncertain":

                return send_workflow_reply(
                    config,
                    request.message,
                    outcome="customer_intent_uncertain_draft_preserved",
                    draft=draft,
                    details={
                        "draft_changed": False,
                        "draft_submitted": False,
                        "next_step": (
                            "Ask whether the customer wants "
                            "to edit, submit, or discard "
                            "the prepared request"
                        )
                    }
                )

            # -------------------------------------
            # F. Handle modification
            # -------------------------------------

            if modification_decision == "modify":

                # First version: cancellation edits only
                if action_type != "cancellation":

                    return send_workflow_reply(
                        config,
                        request.message,
                        outcome="requested_draft_edit_not_yet_supported",
                        draft=draft,
                        details={
                            "draft_changed": False,
                            "draft_submitted": False,
                            "next_step": (
                                "Explain that this type of draft "
                                "cannot currently be edited. "
                                "Preserve the original draft."
                            )
                        }
                    )

                # Extract cancellation edit details
                try:

                    edit = extract_cancellation_edit(
                        request.message
                    )

                except Exception as exc:

                    raise HTTPException(
                        status_code=503,
                        detail="Unable to extract cancellation edit"
                    ) from exc

                print(
                    "CANCELLATION EDIT:",
                    edit.action,
                    edit.new_reason,
                    flush=True
                )

                # ---------------------------------
                # F1. Reason modification
                # ---------------------------------

                if edit.action == "edit_reason":

                    proposed_reason = (edit.new_reason or "").strip()

                    # If the extractor returned the entire customer
                    # instruction as the replacement reason,
                    # don't automatically update the draft.
                    if (
                        proposed_reason
                        and proposed_reason.casefold()
                        != request.message.strip().casefold()
                    ):
                        return update_cancellation_reason(
                            config,
                            request.message,
                            proposed_reason
                        )

                    # No trustworthy replacement was extracted.
                    # Enter editing mode and ask for the reason.
                    return send_workflow_reply(
                        config,
                        request.message,
                        outcome="awaiting_replacement_reason",
                        draft=draft,
                        details={
                            "draft_changed": False,
                            "draft_submitted": False,
                            "next_step": (
                                "Ask the customer to provide "
                                "their new cancellation reason"
                            )
                        },
                        pending_edit="cancellation_reason"
                    )


                # ---------------------------------
                # F2. Another field
                # ---------------------------------

                if edit.action == "other_field":

                    return send_workflow_reply(
                        config,
                        request.message,
                        outcome="requested_field_edit_not_supported",
                        draft=draft,
                        details={
                            "supported_field": "reason",
                            "draft_changed": False,
                            "draft_submitted": False,
                            "next_step": (
                                "Explain that only the "
                                "cancellation reason can "
                                "currently be edited"
                            )
                        }
                    )

                # ---------------------------------
                # F3. Unclear field
                # ---------------------------------

                return send_workflow_reply(
                    config,
                    request.message,
                    outcome="modification_field_unclear",
                    draft=draft,
                    details={
                        "draft_changed": False,
                        "draft_submitted": False,
                        "next_step": (
                            "Ask which field the customer "
                            "wants to change"
                        )
                    }
                )

            # -------------------------------------
            # G. Original V3 confirmation classifier
            # -------------------------------------

            # Reached only when the modification
            # detector returns "not_modify"

            if modification_decision != "not_modify":
                raise HTTPException(
                    status_code=503,
                    detail="Unexpected modification decision"
                )

            try:

                intent = confirmation_llm.invoke([
                    (
                        "system",
                        CONFIRMATION_SYSTEM_PROMPT
                    ),
                    (
                        "human",
                        request.message
                    )
                ])

            except Exception as exc:

                raise HTTPException(
                    status_code=503,
                    detail="Unable to interpret confirmation"
                ) from exc

            decision = intent.decision

            print(
                "CONFIRMATION INTENT:",
                decision,
                flush=True
            )

            # -------------------------------------
            # H. Customer discards pending draft
            # -------------------------------------

            if decision == "cancel":

                with submission_lock:

                    current_state = agent.get_state(
                        config
                    ).values

                    if current_state.get(state_key) is None:
                        raise HTTPException(
                            status_code=409,
                            detail="Request already handled"
                        )

                    # Factual receipt; no database write
                    reply = (
                        f"Okay, your {action_type} draft "
                        "has been discarded. "
                        "Nothing was submitted."
                    )

                    save_chat_response(
                        config,
                        request.message,
                        reply,
                        **{
                            state_key: None,
                            "pending_edit": None
                        }
                    )

                return {"reply": reply}

            # -------------------------------------
            # I. Customer confirms submission
            # -------------------------------------

            if decision == "confirm":

                with submission_lock:

                    current_state = agent.get_state(
                        config
                    ).values

                    current_draft = current_state.get(
                        state_key
                    )

                    if current_draft is None:
                        raise HTTPException(
                            status_code=409,
                            detail="Request already handled"
                        )

                    # Call existing FastAPI endpoint
                    try:

                        response = httpx.post(
                            endpoint,
                            json=current_draft,
                            timeout=15.0
                        )

                    except httpx.RequestError as exc:

                        raise HTTPException(
                            status_code=503,
                            detail="Unable to reach the API"
                        ) from exc

                    if response.status_code != 201:

                        try:
                            error_data = response.json()

                            error_detail = (
                                error_data.get(
                                    "detail",
                                    "Request submission failed"
                                )
                                if isinstance(error_data, dict)
                                else "Request submission failed"
                            )

                        except ValueError:
                            error_detail = (
                                "Request submission failed"
                            )

                        raise HTTPException(
                            status_code=response.status_code,
                            detail=error_detail
                        )

                    created = response.json()

                    # Verified API receipt:
                    # We avoid another model call after
                    # successful submission, so an LLM
                    # failure cannot delay state clearing.

                    if action_type == "ticket":

                        reply = (
                            "Your support ticket was "
                            "created successfully! "
                            f"Ticket ID: {created['ticket_id']}. "
                            f"Status: {created['status']}."
                        )

                    elif action_type == "refund":

                        reply = (
                            "Your refund request was "
                            "submitted successfully! "
                            f"Refund ID: {created['refund_id']}. "
                            f"Status: {created['status']}."
                        )

                    else:

                        reply = (
                            "Your order cancellation request "
                            "was submitted successfully! "
                            f"Cancellation ID: "
                            f"{created['cancellation_id']}. "
                            f"Status: {created['status']}. "
                            "The order itself has not "
                            "been cancelled yet."
                        )

                    # Clear the pending draft
                    save_chat_response(
                        config,
                        request.message,
                        reply,
                        **{
                            state_key: None,
                            "pending_edit": None
                        }
                    )

                    return {"reply": reply}

            # -------------------------------------
            # J. Unclear confirmation
            # -------------------------------------

            return send_workflow_reply(
                config,
                request.message,
                outcome="request_awaiting_confirmation",
                draft=draft,
                details={
                    "draft_changed": False,
                    "draft_submitted": False,
                    "next_step": (
                        "Clarify the customer's question "
                        "or ask for their submission decision"
                    )
                }
            )

        # -------------------------------------
        # K. No pending request
        #    Normal LangGraph conversation
        # -------------------------------------

        if pending_edit is not None:
            raise HTTPException(
                status_code=409,
                detail="Editing state exists without a draft"
            )

        previous_count = len(
            saved_state.get("messages", [])
        )

        result = agent.invoke(
            {
                "messages": [
                    HumanMessage(content=request.message)
                ]
            },
            config=config
        )

        reply = result["messages"][-1].content

        # -------------------------------------
        # L. Clean model response
        # -------------------------------------

        if not isinstance(reply, str):
            raise HTTPException(
                status_code=502,
                detail="Invalid model response"
            )

        if "</think>" in reply:
            reply = reply.rsplit(
                "</think>", 1
            )[-1].strip()

        if "<think>" in reply or not reply:
            raise HTTPException(
                status_code=502,
                detail="The model did not produce a clean answer"
            )

        # -------------------------------------
        # M. Detect prepared request drafts
        # -------------------------------------

        new_messages = result["messages"][
            previous_count:
        ]

        prepared_drafts = []

        for message in new_messages:

            if not isinstance(message, ToolMessage):
                continue

            if message.name not in (
                "prepare_support_ticket",
                "prepare_refund_request",
                "prepare_cancellation_request"
            ):
                continue

            try:
                data = json.loads(message.content)

            except (ValueError, TypeError):
                continue

            if not data.get("confirmation_required"):
                continue

            draft = data.get("draft")

            if not isinstance(draft, dict):
                continue

            prepared_drafts.append({
                "tool": message.name,
                "draft": draft
            })

        # Multiple drafts should not be submitted
        if len(prepared_drafts) > 1:

            reply = (
                "I prepared multiple requests. "
                "Please tell me which one you'd "
                "like to handle first."
            )

            agent.update_state(
                config,
                {
                    "messages": [
                        AIMessage(
                            id=result["messages"][-1].id,
                            content=reply
                        )
                    ]
                }
            )

            return {"reply": reply}

        # -------------------------------------
        # N. Save one new draft
        # -------------------------------------

        if len(prepared_drafts) == 1:

            prepared = prepared_drafts[0]
            draft = prepared["draft"]

            if prepared["tool"] == "prepare_support_ticket":

                state_key = "pending_ticket"

                reply = (
                    "I've prepared your support ticket:\n\n"
                    f"Subject: {draft['subject']}\n"
                    f"Description: {draft['description']}\n"
                    f"Customer ID: {draft['customer_id']}\n"
                    f"Order ID: "
                    f"{draft['order_id'] or 'Not provided'}\n\n"
                    "Should I submit this ticket?"
                )

            elif prepared["tool"] == "prepare_refund_request":

                state_key = "pending_refund"

                reply = (
                    "I've prepared your refund request:\n\n"
                    f"Order ID: {draft['order_id']}\n"
                    f"Amount: {draft['amount']}\n"
                    f"Reason: {draft['reason']}\n\n"
                    "Should I submit this refund request?"
                )

            else:

                state_key = "pending_cancellation"

                reply = (
                    "I've prepared your cancellation request:\n\n"
                    f"Order ID: {draft['order_id']}\n"
                    f"Reason: "
                    f"{draft['reason'] or 'Not provided'}\n\n"
                    "Should I submit this cancellation request? "
                    "It will require admin approval."
                )

            # Save draft and replace final AI message
            agent.update_state(
                config,
                {
                    state_key: draft,
                    "messages": [
                        AIMessage(
                            id=result["messages"][-1].id,
                            content=reply
                        )
                    ]
                }
            )

        return {"reply": reply}

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "CHAT ERROR:",
            repr(exc),
            flush=True
        )

        raise HTTPException(
            status_code=503,
            detail="Unable to process the chat request"
        ) from exc
