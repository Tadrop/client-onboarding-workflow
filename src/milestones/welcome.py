"""Milestone 1 — Welcome email + questionnaire + Calendly link.

External comm: drafted, awaiting AM approval. Internal-only side effects
(creating the Typeform link, creating the Calendly link) run unconditionally
since they don't reach the client.
"""

from __future__ import annotations

from ..drafter.welcome import draft_welcome_email
from ..integrations import IntegrationBundle
from ..logging_setup import get_logger
from ..schemas import (
    AMReview,
    MilestoneName,
    MilestoneState,
    OnboardingRun,
    ReviewDecision,
)
from ..state import Store
from ..state.idempotency import run_idempotent
from ..state.transitions import transition

log = get_logger(__name__)


def run(run: OnboardingRun, store: Store, clients: IntegrationBundle) -> None:
    transition(store, run, MilestoneName.WELCOME, MilestoneState.RUNNING)

    primary_email = (
        run.contract.client_contacts[0].email
        if run.contract.client_contacts
        else "client@example.com"
    )

    questionnaire = run_idempotent(
        store,
        run.run_id,
        MilestoneName.WELCOME,
        "typeform_link",
        lambda: _serialize_questionnaire(
            clients.typeform.questionnaire_link(run.contract.client_name, primary_email)
        ),
    )

    calendly = run_idempotent(
        store,
        run.run_id,
        MilestoneName.WELCOME,
        "calendly_link",
        lambda: _serialize_calendly(
            clients.calendly.scheduling_link(run.contract.client_name, primary_email)
        ),
    )

    # Draft the email — idempotency cached by milestone (re-running returns
    # the same draft body even if the LLM is non-deterministic).
    draft_payload = run_idempotent(
        store,
        run.run_id,
        MilestoneName.WELCOME,
        "draft_email",
        lambda: _draft_and_persist(run, store, questionnaire["url"], calendly["url"]),
    )

    # Queue review (idempotent: re-running attaches no second review row).
    run_idempotent(
        store,
        run.run_id,
        MilestoneName.WELCOME,
        "queue_review",
        lambda: _queue_review(store, run, draft_payload["draft_id"]),
    )

    transition(
        store,
        run,
        MilestoneName.WELCOME,
        MilestoneState.AWAITING_APPROVAL,
        artifacts={
            "questionnaire_form_id": questionnaire["form_id"],
            "calendly_event_type_uri": calendly["event_type_uri"],
            "draft_id": draft_payload["draft_id"],
        },
    )


def _serialize_questionnaire(link) -> dict:  # type: ignore[no-untyped-def]
    return {"url": link.url, "form_id": link.form_id}


def _serialize_calendly(link) -> dict:  # type: ignore[no-untyped-def]
    return {"url": link.url, "event_type_uri": link.event_type_uri}


def _draft_and_persist(run: OnboardingRun, store: Store, q_url: str, c_url: str) -> dict:
    draft = draft_welcome_email(
        run_id=run.run_id,
        contract=run.contract,
        questionnaire_url=q_url,
        calendly_url=c_url,
    )
    store.save_draft(draft)
    return {"draft_id": draft.draft_id}


def _queue_review(store: Store, run: OnboardingRun, draft_id: str) -> dict:
    review = AMReview(
        run_id=run.run_id,
        milestone=MilestoneName.WELCOME,
        draft_id=draft_id,
        decision=ReviewDecision.PENDING,
    )
    store.save_review(review)
    return {"review_id": review.review_id}
