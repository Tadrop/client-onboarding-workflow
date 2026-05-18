"""State machine for milestone transitions.

Legal transitions:

    ready             → running, skipped
    running           → awaiting_approval, done, failed
    awaiting_approval → done, failed, running   (re-run after rejection)
    failed            → running                 (retry)
    done              → done                    (idempotent no-op)
    skipped           → skipped                 (idempotent no-op)

Anything else is rejected with `IllegalTransition`.
"""

from __future__ import annotations

from ..schemas import MilestoneState

_ALLOWED: dict[MilestoneState, set[MilestoneState]] = {
    MilestoneState.READY: {MilestoneState.RUNNING, MilestoneState.SKIPPED},
    MilestoneState.RUNNING: {
        MilestoneState.AWAITING_APPROVAL,
        MilestoneState.DONE,
        MilestoneState.FAILED,
    },
    MilestoneState.AWAITING_APPROVAL: {
        MilestoneState.DONE,
        MilestoneState.FAILED,
        MilestoneState.RUNNING,
    },
    MilestoneState.FAILED: {MilestoneState.RUNNING},
    MilestoneState.DONE: {MilestoneState.DONE},
    MilestoneState.SKIPPED: {MilestoneState.SKIPPED},
}


class IllegalTransition(Exception):
    def __init__(self, src: MilestoneState, dst: MilestoneState) -> None:
        super().__init__(f"illegal milestone transition: {src.value} → {dst.value}")
        self.src = src
        self.dst = dst


class StateMachine:
    @staticmethod
    def assert_legal(src: MilestoneState, dst: MilestoneState) -> None:
        if dst not in _ALLOWED.get(src, set()):
            raise IllegalTransition(src, dst)
