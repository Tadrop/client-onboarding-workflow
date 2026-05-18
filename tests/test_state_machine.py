"""Legal/illegal transitions and durable persistence."""

from __future__ import annotations

import pytest

from src.schemas import Milestone, MilestoneName, MilestoneState, OnboardingRun
from src.state import IllegalTransition, StateMachine
from src.state.transitions import transition

from .fixtures.contracts import new_contract


def test_legal_transitions() -> None:
    sm = StateMachine()
    sm.assert_legal(MilestoneState.READY, MilestoneState.RUNNING)
    sm.assert_legal(MilestoneState.RUNNING, MilestoneState.AWAITING_APPROVAL)
    sm.assert_legal(MilestoneState.AWAITING_APPROVAL, MilestoneState.DONE)
    sm.assert_legal(MilestoneState.FAILED, MilestoneState.RUNNING)


def test_illegal_transition_raises() -> None:
    sm = StateMachine()
    with pytest.raises(IllegalTransition):
        sm.assert_legal(MilestoneState.READY, MilestoneState.DONE)
    with pytest.raises(IllegalTransition):
        sm.assert_legal(MilestoneState.DONE, MilestoneState.RUNNING)


def test_transition_persists_to_store_before_returning(store) -> None:
    contract = new_contract()
    run = OnboardingRun(
        contract=contract,
        milestones={MilestoneName.WELCOME: Milestone(name=MilestoneName.WELCOME)},
    )
    store.save_run(run)

    transition(store, run, MilestoneName.WELCOME, MilestoneState.RUNNING)
    reloaded = store.get_run(run.run_id)
    assert reloaded is not None
    assert reloaded.milestones[MilestoneName.WELCOME].state is MilestoneState.RUNNING
    assert reloaded.milestones[MilestoneName.WELCOME].attempts == 1
