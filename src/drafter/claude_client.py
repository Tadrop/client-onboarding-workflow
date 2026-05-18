"""Anthropic client wrapper.

When `ANTHROPIC_API_KEY` is unset (the default in CI/dev), `complete()` calls
the registered offline fallback so the rest of the pipeline can run without
credentials. Tests inject deterministic fallbacks via `set_offline_fallback`.
"""

from __future__ import annotations

from collections.abc import Callable

from ..config import get_settings
from ..logging_setup import get_logger

log = get_logger(__name__)


_OfflineFn = Callable[[str, str], str]
_offline_fallback: _OfflineFn | None = None


def set_offline_fallback(fn: _OfflineFn | None) -> None:
    """Register a `(system, user) -> text` fallback used when no API key is set."""
    global _offline_fallback
    _offline_fallback = fn


def complete(system: str, user: str, *, max_tokens: int = 1024) -> str:
    """Single-turn completion. Returns the assistant text."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        if _offline_fallback is None:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set and no offline fallback is registered. "
                "Call drafter.claude_client.set_offline_fallback() in tests/dev mode."
            )
        log.info("claude.offline_fallback")
        return _offline_fallback(system, user)

    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("anthropic package not installed") from e

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()
