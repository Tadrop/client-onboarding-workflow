"""Milestone 5 — Polite checklist reminder if assets/info are missing.

Runs only when `now >= run.created_at + reminder_days` AND the AM has flagged
missing items via the review API. Emits an AM-gated draft.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import get_settings
from ..drafter.reminder import draft_reminder
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
    missing_items: list[str] | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    settings = get_settings()
    created = run.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    deadline = created + timedelta(days=settings.reminder_days)
    if now < deadline:
        log.info("reminder.waiting", run_id=run.run_id, deadline=deadline.isoformat())
        return

    items = missing_items or _infer_missing(run)
    if not items:
        # Nothing to remind about — mark skipped so the flow can complete.
        transition(store, run, MilestoneName.REMINDER, MilestoneState.SKIPPED)
        return

    transition(store, run, MilestoneName.REMINDER, MilestoneState.RUNNING)

    draft_payload = run_idempotent(
        store,
        run.run_id,
        MilestoneName.REMINDER,
        "draft_reminder",
        lambda: _draft_and_persist(run, store, items),
    )
    run_idempotent(
        store,
        run.run_id,
        MilestoneName.REMINDER,
        "queue_review",
        lambda: _queue_review(store, run, draft_payload["draft_id"]),
    )
    transition(
        store,
        run,
        MilestoneName.REMINDER,
        MilestoneState.AWAITING_APPROVAL,
        artifacts={"draft_id": draft_payload["draft_id"], "missing_items": items},
    )


def _infer_missing(run: OnboardingRun) -> list[str]:
    """Default heuristic: questionnaire never returned → flag that."""
    welcome = run.milestones.get(MilestoneName.WELCOME)
    if not welcome:
        return []
    brief = run.milestones.get(MilestoneName.BRIEF)
    if brief and brief.artifacts.get("mode") == "am_fill_in":
        return ["onboarding questionnaire answers"]
    return []


def _draft_and_persist(run: OnboardingRun, store: Store, items: list[str]) -> dict:
    draft = draft_reminder(run_id=run.run_id, contract=run.contract, missing_items=items)
    store.save_draft(draft)
    return {"draft_id": draft.draft_id}


def _queue_review(store: Store, run: OnboardingRun, draft_id: str) -> dict:
    review = AMReview(
        run_id=run.run_id,
        milestone=MilestoneName.REMINDER,
        draft_id=draft_id,
        decision=ReviewDecision.PENDING,
    )
    store.save_review(review)
    return {"review_id": review.review_id}
