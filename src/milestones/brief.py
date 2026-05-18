"""Milestone 4 — Project brief draft (questionnaire-driven OR degrade).

Looks up the Typeform form_id captured by the welcome milestone, fetches the
response, and:

  - If submitted → draft from the answers.
  - If unsubmitted AND now ≥ welcome.created_at + degrade_days → draft in
    AM-fill-in mode with `[AM TO FILL: …]` placeholders.
  - Otherwise (still within the window) → leave `ready` and bail.

Output is queued as a `Draft` for AM review (brief is internal but still
gated — the AM owns the voice).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import get_settings
from ..drafter.brief import draft_brief
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


def run(
    run: OnboardingRun,
    store: Store,
    clients: IntegrationBundle,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    settings = get_settings()

    welcome = run.milestones.get(MilestoneName.WELCOME)
    form_id = welcome.artifacts.get("questionnaire_form_id") if welcome else None
    primary_email = (
        run.contract.client_contacts[0].email
        if run.contract.client_contacts
        else "client@example.com"
    )

    response = clients.typeform.fetch_response(form_id, primary_email) if form_id else None

    if response is None or not response.submitted:
        welcome_time = welcome.updated_at if welcome else run.created_at
        if welcome_time.tzinfo is None:
            welcome_time = welcome_time.replace(tzinfo=timezone.utc)
        deadline = welcome_time + timedelta(days=settings.questionnaire_degrade_days)
        if now < deadline:
            log.info(
                "brief.waiting_for_questionnaire",
                run_id=run.run_id,
                deadline=deadline.isoformat(),
            )
            return
        # Degrade.
        answers = None
    else:
        answers = response.answers

    transition(store, run, MilestoneName.BRIEF, MilestoneState.RUNNING)

    draft_payload = run_idempotent(
        store,
        run.run_id,
        MilestoneName.BRIEF,
        "draft_brief",
        lambda: _draft_and_persist(run, store, answers),
    )

    run_idempotent(
        store,
        run.run_id,
        MilestoneName.BRIEF,
        "queue_review",
        lambda: _queue_review(store, run, draft_payload["draft_id"]),
    )

    transition(
        store,
        run,
        MilestoneName.BRIEF,
        MilestoneState.AWAITING_APPROVAL,
        artifacts={
            "mode": "am_fill_in" if answers is None else "from_answers",
            "draft_id": draft_payload["draft_id"],
        },
    )


def _draft_and_persist(run: OnboardingRun, store: Store, answers: dict[str, str] | None) -> dict:
    draft = draft_brief(run_id=run.run_id, contract=run.contract, answers=answers)
    store.save_draft(draft)
    return {"draft_id": draft.draft_id}


def _queue_review(store: Store, run: OnboardingRun, draft_id: str) -> dict:
    review = AMReview(
        run_id=run.run_id,
        milestone=MilestoneName.BRIEF,
        draft_id=draft_id,
        decision=ReviewDecision.PENDING,
    )
    store.save_review(review)
    return {"review_id": review.review_id}
