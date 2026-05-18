"""[SAFETY] External client emails are gated by AM approval state."""

from __future__ import annotations

from src.milestones.orchestrator import approve_and_continue, start_run
from src.schemas import (
    DraftKind,
    MilestoneName,
    MilestoneState,
    ReviewDecision,
)

from .fixtures.contracts import new_contract


def test_welcome_email_is_drafted_not_sent(store, clients) -> None:
    contract = new_contract()
    run = start_run(contract, store=store, clients=clients)

    # Welcome must be in awaiting_approval — never auto-done.
    assert run.milestones[MilestoneName.WELCOME].state is MilestoneState.AWAITING_APPROVAL

    drafts = store.drafts_for_run(run.run_id)
    assert any(d.kind is DraftKind.WELCOME_EMAIL for d in drafts)

    reviews = store.list_pending_reviews()
    assert any(r.milestone is MilestoneName.WELCOME for r in reviews)


def test_pipeline_blocks_at_welcome_until_approved(store, clients) -> None:
    contract = new_contract(envelope_id="env_block_001")
    run = start_run(contract, store=store, clients=clients)
    # internal_setup must NOT have started yet.
    assert run.milestones[MilestoneName.INTERNAL_SETUP].state is MilestoneState.READY

    approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)
    fresh = store.get_run(run.run_id)
    assert fresh.milestones[MilestoneName.WELCOME].state is MilestoneState.DONE
    assert fresh.milestones[MilestoneName.INTERNAL_SETUP].state is MilestoneState.DONE


def test_review_record_starts_pending(store, clients) -> None:
    contract = new_contract(envelope_id="env_pending_001")
    start_run(contract, store=store, clients=clients)
    for review in store.list_pending_reviews():
        assert review.decision is ReviewDecision.PENDING
        assert review.decided_at is None
