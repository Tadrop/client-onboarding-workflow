"""Durable state for onboarding runs.

Two responsibilities live here:

1. `Store` — persists `OnboardingRun`, `Draft`, `AMReview`, and idempotency
   records to SQLite. Transitions are written BEFORE the side effect, so a
   crash mid-step leaves a recoverable record.

2. `StateMachine` — enforces the legal transitions
   `ready → running → awaiting_approval → done | failed`.
"""

from .machine import IllegalTransition, StateMachine
from .store import Store, get_store, reset_store_cache

__all__ = ["Store", "get_store", "reset_store_cache", "StateMachine", "IllegalTransition"]
