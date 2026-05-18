"""Milestone modules — one per step of the onboarding flow.

Each milestone exposes a `run(run, store, clients) -> None` entry point. It
must:

  - Move its own state via `state.transitions.transition()` BEFORE the side
    effect, so a crash leaves the on-disk state recoverable.
  - Wrap every side effect in idempotency keying so re-runs do not duplicate.
  - Queue a `Draft` (never auto-send) for any external client communication
    and leave the milestone in `awaiting_approval`.
"""
