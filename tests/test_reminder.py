"""Reminder milestone — only fires after the window, only when items missing."""

from __future__ import annotations

from datetime import timedelta

from src.milestones import reminder as reminder_module
from src.milestones.orchestrator import approve_and_continue, start_run
from src.schemas import DraftKind, MilestoneName, MilestoneState

from .fixtures.contracts import new_contract


def test_reminder_skips_when_nothing_is_missing(store, clients) -> None:
    contract = new_contract()
    run = start_run(contract, store=store, clients=clients)
    approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)
    run = store.get_run(run.run_id)

    now = run.created_at + timedelta(days=5)
    reminder_module.run(run, store, clients, now=now, missing_items=[])

    fresh = store.get_run(run.run_id)
    assert fresh.milestones[MilestoneName.REMINDER].state is MilestoneState.SKIPPED


def test_reminder_drafts_when_assets_missing(store, clients) -> None:
    contract = new_contract(envelope_id="env_remind_001")
    run = start_run(contract, store=store, clients=clients)
    approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)
    run = store.get_run(run.run_id)

    now = run.created_at + timedelta(days=5)
    reminder_module.run(
        run, store, clients, now=now, missing_items=["brand assets", "voice samples"]
    )
    fresh = store.get_run(run.run_id)
    assert fresh.milestones[MilestoneName.REMINDER].state is MilestoneState.AWAITING_APPROVAL

    drafts = [d for d in store.drafts_for_run(run.run_id) if d.kind is DraftKind.REMINDER]
    assert drafts
    assert "brand assets" in drafts[0].body or "[AM TO FILL:" in drafts[0].body
