"""[SAFETY/RENEWAL] Renewal contracts must NEVER trigger the welcome email."""

from __future__ import annotations

from src.milestones.orchestrator import start_run
from src.schemas import DraftKind, MilestoneName

from .fixtures.contracts import renewal_contract


def test_renewal_contract_never_triggers_welcome_email(store, clients) -> None:
    contract = renewal_contract()
    run = start_run(contract, store=store, clients=clients)

    # No welcome milestone should be present at all.
    assert MilestoneName.WELCOME not in run.milestones
    assert MilestoneName.KICKOFF not in run.milestones

    # No drafts of any kind should exist (renewal never queues client comms).
    drafts = store.drafts_for_run(run.run_id)
    assert drafts == []

    # And no welcome-email drafts in storage at all.
    all_runs = store.list_runs()
    for r in all_runs:
        for d in store.drafts_for_run(r.run_id):
            assert d.kind is not DraftKind.WELCOME_EMAIL


def test_renewal_contract_resembling_new_still_routes_renewal(store, clients) -> None:
    """A renewal contract with `service_type=branding` (not retainer) must still
    be classified as renewal via the `existing_client_id` rule."""
    contract = renewal_contract(
        envelope_id="env_renewal_resemble_001",
        raw_metadata={"existing_client_id": "cli_acme_001"},
    )
    # Strip explicit contract_type to force ambiguity:
    from src.schemas import ContractType

    contract.contract_type = ContractType.NEW
    contract.raw_metadata.pop("contract_type", None)
    run = start_run(contract, store=store, clients=clients)
    assert MilestoneName.WELCOME not in run.milestones
