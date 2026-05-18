"""Idempotency helper used by integration modules.

Usage:

    @idempotent(run_id=run.run_id, milestone=MilestoneName.INTERNAL_SETUP, step="slack_channel")
    def create_channel(...) -> dict:
        ...

The wrapped function only runs the first time; subsequent calls with the same
key return the stored result.

NOTE: the stored result must be JSON-serializable (it's a `dict[str, Any]`).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from ..logging_setup import get_logger
from ..schemas import MilestoneName
from .store import Store

log = get_logger(__name__)


def idempotent(
    store: Store,
    run_id: str,
    milestone: MilestoneName,
    step: str,
) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            cached = store.get_idempotent(run_id, milestone, step)
            if cached is not None:
                log.info(
                    "idempotent.hit",
                    run_id=run_id,
                    milestone=milestone.value,
                    step=step,
                )
                return cached
            result = fn(*args, **kwargs)
            store.put_idempotent(run_id, milestone, step, result)
            return result

        return wrapper

    return decorator


def run_idempotent(
    store: Store,
    run_id: str,
    milestone: MilestoneName,
    step: str,
    fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Functional form for one-off calls (no decorator needed)."""
    cached = store.get_idempotent(run_id, milestone, step)
    if cached is not None:
        log.info("idempotent.hit", run_id=run_id, milestone=milestone.value, step=step)
        return cached
    result = fn()
    store.put_idempotent(run_id, milestone, step, result)
    return result
