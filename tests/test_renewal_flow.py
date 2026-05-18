"""End-to-end renewal flow — refresh setup runs, no client comms."""

from __future__ import annotations

from src.milestones.orchestrator import start_run
from src.schemas import MilestoneName, MilestoneState

from .fixtures.contracts import renewal_contract


def test_renewal_flow_completes_autonomously(store, clients) -> None:
    contract = renewal_contract()
    run = start_run(contract, store=store, clients=clients)
    fresh = store.get_run(run.run_id)
    refresh = fresh.milestones[MilestoneName.RENEWAL_REFRESH]
    assert refresh.state is MilestoneState.DONE
    assert "refreshed_at" in refresh.artifacts

    # No reviews queued — renewal touches no external comms.
    assert store.list_pending_reviews() == []
    assert store.drafts_for_run(run.run_id) == []
