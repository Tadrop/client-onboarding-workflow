"""Slack channel + invite client.

Naming convention is config-driven (`config/slack_naming.yaml`). The real
client would call `conversations.create`, `conversations.invite`, etc.;
the mock keeps an in-memory channel registry so collision/idempotency tests
can run without a workspace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from ..config import CONFIG_DIR, get_settings
from .base import SlackChannelCollisionError


@dataclass
class SlackChannel:
    id: str
    name: str
    invited_emails: list[str] = field(default_factory=list)


class SlackClient(Protocol):
    def slugify(self, client_name: str) -> str: ...
    def channel_name(self, client_name: str, service_type: str) -> str: ...
    def create_channel(self, name: str) -> SlackChannel: ...
    def invite(self, channel_id: str, emails: list[str]) -> SlackChannel: ...
    def post_message(self, channel_id: str, text: str) -> None: ...


def _load_naming() -> dict:
    with (CONFIG_DIR / "slack_naming.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class MockSlackClient:
    """Deterministic in-memory Slack client for dev, tests, and demos."""

    def __init__(self) -> None:
        self._channels: dict[str, SlackChannel] = {}  # name → channel
        self._naming = _load_naming()
        self._messages: list[tuple[str, str]] = []

    # ─── naming ──────────────────────────────────────────────────────────────

    def slugify(self, client_name: str) -> str:
        rules = self._naming["slug"]
        s = client_name
        if rules.get("lowercase", True):
            s = s.lower()
        for ch in rules.get("strip_chars", ""):
            s = s.replace(ch, "")
        s = re.sub(r"\s+", rules.get("separator", "-"), s.strip())
        s = re.sub(r"[^a-z0-9-]", "", s)
        s = re.sub(r"-+", "-", s).strip("-")
        return s or "client"

    def channel_name(self, client_name: str, service_type: str) -> str:
        prefix = get_settings().slack_channel_prefix or self._naming["default_prefix"]
        return f"{prefix}-{self.slugify(client_name)}-{service_type}"

    # ─── operations ──────────────────────────────────────────────────────────

    def create_channel(self, name: str) -> SlackChannel:
        if name in self._channels:
            # Real Slack returns `name_taken` — we surface as a collision so
            # milestone code can append a suffix.
            existing = self._channels[name]
            collision_name, channel = self._resolve_collision(name)
            self._channels[collision_name] = channel
            channel.invited_emails = []  # fresh channel
            # Avoid double-storing the existing one.
            assert existing.name == name
            return channel
        channel = SlackChannel(id=f"C{len(self._channels) + 1:05d}", name=name)
        self._channels[name] = channel
        return channel

    def _resolve_collision(self, base: str) -> tuple[str, SlackChannel]:
        max_suffix = int(self._naming.get("max_suffix", 9))
        for i in range(2, max_suffix + 2):
            candidate = f"{base}-{i}"
            if candidate not in self._channels:
                channel = SlackChannel(id=f"C{len(self._channels) + 1:05d}", name=candidate)
                return candidate, channel
        raise SlackChannelCollisionError(
            f"could not find free Slack channel name for base={base!r}"
        )

    def invite(self, channel_id: str, emails: list[str]) -> SlackChannel:
        channel = next((c for c in self._channels.values() if c.id == channel_id), None)
        if channel is None:
            raise LookupError(f"unknown slack channel id: {channel_id}")
        for e in emails:
            if e not in channel.invited_emails:
                channel.invited_emails.append(e)
        return channel

    def post_message(self, channel_id: str, text: str) -> None:
        self._messages.append((channel_id, text))

    # ─── inspection helpers (used by tests/dev UI) ───────────────────────────

    @property
    def channels(self) -> dict[str, SlackChannel]:
        return dict(self._channels)

    @property
    def messages(self) -> list[tuple[str, str]]:
        return list(self._messages)


class RealSlackClient:  # pragma: no cover - placeholder for real integration
    """Real Slack API client. Implemented via slack_sdk when credentials are set."""

    def __init__(self, token: str) -> None:
        self._token = token

    def slugify(self, client_name: str) -> str:
        return MockSlackClient().slugify(client_name)

    def channel_name(self, client_name: str, service_type: str) -> str:
        return MockSlackClient().channel_name(client_name, service_type)

    def create_channel(self, name: str) -> SlackChannel:
        raise NotImplementedError(
            "RealSlackClient.create_channel: wire to slack_sdk.WebClient.conversations_create"
        )

    def invite(self, channel_id: str, emails: list[str]) -> SlackChannel:
        raise NotImplementedError(
            "RealSlackClient.invite: wire to slack_sdk.WebClient.conversations_invite"
        )

    def post_message(self, channel_id: str, text: str) -> None:
        raise NotImplementedError(
            "RealSlackClient.post_message: wire to slack_sdk.WebClient.chat_postMessage"
        )


def make_slack_client() -> SlackClient:
    settings = get_settings()
    if settings.mock_integrations or not settings.slack_bot_token:
        return MockSlackClient()
    return RealSlackClient(settings.slack_bot_token)


__all__ = ["SlackClient", "SlackChannel", "MockSlackClient", "RealSlackClient", "make_slack_client"]


# silence unused-import warnings
_ = Path
