"""Milestone transition helper.

Wraps the StateMachine + Store so that every transition is logged AND persisted
BEFORE any side-effect runs. This is the recovery invariant: if the process
crashes after a side-effect, the on-disk state is already `running` and
recovery code can resume from idempotent steps.
"""

from __future__ import annotations

from typing import Any

from ..logging_setup import get_logger
from ..schemas import MilestoneName, MilestoneState, OnboardingRun
from .machine import StateMachine
from .store import Store

log = get_logger(__name__)


def transition(
    store: Store,
    run: OnboardingRun,
    milestone: MilestoneName,
    new_state: MilestoneState,
    *,
    error: str | None = None,
    artifacts: dict[str, Any] | None = None,
) -> OnboardingRun:
    """Move `milestone` to `new_state`, persisting BEFORE the caller's side effect."""
    m = run.get(milestone)
    old_state = m.state
    StateMachine.assert_legal(old_state, new_state)

    if new_state is MilestoneState.RUNNING:
        m.attempts += 1
        m.last_error = None
    if error is not None:
        m.last_error = error
    if artifacts:
        m.artifacts.update(artifacts)

    m.transition(new_state)
    store.save_run(run)

    log.info(
        "milestone.transition",
        run_id=run.run_id,
        milestone=milestone.value,
        old_state=old_state.value,
        new_state=new_state.value,
        attempts=m.attempts,
    )
    return run
