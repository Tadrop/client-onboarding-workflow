"""The orchestrator drives a run through its milestone sequence.

Two entry points:

  - `start_run(contract)` — classify, build the run, run the first batch of
    autonomous milestones.
  - `resume_run(run_id)` — advance a run that was waiting on AM approval or
    a time-based gate (questionnaire degrade, reminder window).

Autonomous milestones run unconditionally. External-comm milestones leave the
run `awaiting_approval` and stop; nothing more runs until the AM approves.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..integrations import IntegrationBundle, get_clients
from ..logging_setup import get_logger
from ..router import get_classifier
from ..schemas import (
    Contract,
    ContractType,
    Milestone,
    MilestoneName,
    MilestoneState,
    OnboardingRun,
    milestones_for,
)
from ..state import Store, get_store
from . import brief as brief_module
from . import internal_setup as internal_setup_module
from . import kickoff as kickoff_module
from . import reminder as reminder_module
from . import renewal as renewal_module
from . import welcome as welcome_module

log = get_logger(__name__)


def start_run(
    contract: Contract,
    *,
    store: Store | None = None,
    clients: IntegrationBundle | None = None,
) -> OnboardingRun:
    store = store or get_store()
    clients = clients or get_clients()

    existing = store.find_run_by_envelope(contract.envelope_id)
    if existing:
        log.info(
            "orchestrator.duplicate_envelope",
            envelope_id=contract.envelope_id,
            run_id=existing.run_id,
        )
        return existing

    classification = get_classifier().classify(contract)
    contract.contract_type = classification.contract_type
    log.info(
        "orchestrator.classified",
        envelope_id=contract.envelope_id,
        contract_type=classification.contract_type.value,
        rule=classification.rule_name,
    )

    milestones = {name: Milestone(name=name) for name in milestones_for(contract.contract_type)}
    run = OnboardingRun(contract=contract, milestones=milestones)
    store.save_run(run)
    _advance(run, store, clients)
    return run


def resume_run(
    run_id: str,
    *,
    store: Store | None = None,
    clients: IntegrationBundle | None = None,
    now: datetime | None = None,
) -> OnboardingRun:
    store = store or get_store()
    clients = clients or get_clients()
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"unknown run: {run_id}")
    _advance(run, store, clients, now=now)
    return run


def _advance(
    run: OnboardingRun,
    store: Store,
    clients: IntegrationBundle,
    *,
    now: datetime | None = None,
) -> None:
    """Walk milestones in order, running each that's `ready`.

    Stops on the first milestone that lands in `awaiting_approval`, `failed`,
    or that bails (e.g. brief still inside the degrade window).
    """
    if run.contract.contract_type is ContractType.RENEWAL:
        sequence = [MilestoneName.RENEWAL_REFRESH]
    else:
        sequence = [
            MilestoneName.WELCOME,
            MilestoneName.INTERNAL_SETUP,
            MilestoneName.KICKOFF,
            MilestoneName.BRIEF,
            MilestoneName.REMINDER,
        ]
    for name in sequence:
        m = run.milestones[name]
        if m.state is MilestoneState.READY:
            _dispatch(name, run, store, clients, now=now)
            # After dispatch, fetch fresh state (run was mutated through transition()).
            m = run.milestones[name]
        if m.state in (MilestoneState.AWAITING_APPROVAL, MilestoneState.FAILED):
            return
        if m.state is MilestoneState.READY:
            # Milestone bailed (e.g. waiting on degrade window). Stop here.
            return


def _dispatch(
    name: MilestoneName,
    run: OnboardingRun,
    store: Store,
    clients: IntegrationBundle,
    *,
    now: datetime | None,
) -> None:
    now = now or datetime.now(timezone.utc)
    if name is MilestoneName.WELCOME:
        welcome_module.run(run, store, clients)
    elif name is MilestoneName.INTERNAL_SETUP:
        internal_setup_module.run(run, store, clients)
    elif name is MilestoneName.KICKOFF:
        kickoff_module.run(run, store, clients)
    elif name is MilestoneName.BRIEF:
        brief_module.run(run, store, clients, now=now)
    elif name is MilestoneName.REMINDER:
        reminder_module.run(run, store, clients, now=now)
    elif name is MilestoneName.RENEWAL_REFRESH:
        renewal_module.run(run, store, clients)
    else:  # pragma: no cover
        raise ValueError(f"unknown milestone: {name}")


def approve_and_continue(
    run_id: str,
    milestone: MilestoneName,
    *,
    store: Store | None = None,
    clients: IntegrationBundle | None = None,
    now: datetime | None = None,
) -> OnboardingRun:
    """AM approved the draft for `milestone` — mark `done` and resume."""
    store = store or get_store()
    clients = clients or get_clients()
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"unknown run: {run_id}")
    m = run.milestones[milestone]
    if m.state is not MilestoneState.AWAITING_APPROVAL:
        log.warning(
            "orchestrator.approve_skipped",
            run_id=run_id,
            milestone=milestone.value,
            state=m.state.value,
        )
        return run
    from ..state.transitions import transition

    transition(store, run, milestone, MilestoneState.DONE)
    _advance(run, store, clients, now=now)
    return run


def reject_and_retry(
    run_id: str,
    milestone: MilestoneName,
    *,
    store: Store | None = None,
    clients: IntegrationBundle | None = None,
) -> OnboardingRun:
    """AM rejected the draft — kick the milestone back to `running` so the
    next call recreates the draft. The previous draft remains in storage."""
    store = store or get_store()
    clients = clients or get_clients()
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"unknown run: {run_id}")
    m = run.milestones[milestone]
    if m.state is not MilestoneState.AWAITING_APPROVAL:
        return run
    from ..state.transitions import transition

    transition(store, run, milestone, MilestoneState.RUNNING)
    transition(store, run, milestone, MilestoneState.FAILED, error="rejected by AM")
    # Caller will re-dispatch when ready; we don't auto-redraft here.
    return run
