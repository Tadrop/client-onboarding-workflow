"""Re-running an interrupted flow must not duplicate Slack/ClickUp/Drive."""

from __future__ import annotations

from src.milestones.orchestrator import start_run
from src.schemas import MilestoneName, MilestoneState

from .fixtures.contracts import new_contract


def test_rerunning_internal_setup_does_not_duplicate(store, clients) -> None:
    contract = new_contract()
    run = start_run(contract, store=store, clients=clients)

    # Welcome is awaiting approval → run is paused. Approve to drive forward
    # through internal_setup.
    from src.milestones.orchestrator import approve_and_continue

    approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)
    fresh = store.get_run(run.run_id)
    assert fresh.milestones[MilestoneName.INTERNAL_SETUP].state is MilestoneState.DONE

    # Snapshot the side-effect set sizes.
    slack_before = len(clients.slack.channels)
    clickup_before = len(clients.clickup.projects)
    drive_before = len(clients.drive.folders)

    # Force a "re-run": flip internal_setup back to ready (simulating a manual
    # operator retry after a crash) and re-trigger.
    from src.milestones.internal_setup import run as run_internal

    fresh.milestones[MilestoneName.INTERNAL_SETUP].state = MilestoneState.READY
    store.save_run(fresh)
    run_internal(fresh, store, clients)

    # Idempotency cache must have caused the integration calls to no-op.
    assert len(clients.slack.channels) == slack_before
    assert len(clients.clickup.projects) == clickup_before
    assert len(clients.drive.folders) == drive_before


def test_repeated_orchestrator_start_returns_same_run(store, clients) -> None:
    contract = new_contract(envelope_id="env_dupe_001")
    run1 = start_run(contract, store=store, clients=clients)
    run2 = start_run(contract, store=store, clients=clients)
    assert run1.run_id == run2.run_id
