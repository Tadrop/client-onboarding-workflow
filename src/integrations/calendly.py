"""Calendly scheduling link generator (mock + real)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from ..config import get_settings


@dataclass
class CalendlyLink:
    url: str
    event_type_uri: str


class CalendlyClient(Protocol):
    def scheduling_link(self, client_name: str, client_email: str) -> CalendlyLink: ...


class MockCalendlyClient:
    def scheduling_link(self, client_name: str, client_email: str) -> CalendlyLink:
        query = urlencode({"name": client_name, "email": client_email})
        return CalendlyLink(
            url=f"https://calendly.com/halo-studio/kickoff?{query}",
            event_type_uri="mock://event-types/kickoff",
        )


class RealCalendlyClient:  # pragma: no cover
    def __init__(self, token: str, event_type_uri: str) -> None:
        self._token = token
        self._event_type_uri = event_type_uri

    def scheduling_link(self, client_name: str, client_email: str) -> CalendlyLink:
        raise NotImplementedError(
            "RealCalendlyClient.scheduling_link: wire to Calendly "
            "POST /scheduling_links with the configured event_type_uri"
        )


def make_calendly_client() -> CalendlyClient:
    settings = get_settings()
    if settings.mock_integrations or not settings.calendly_api_token:
        return MockCalendlyClient()
    return RealCalendlyClient(settings.calendly_api_token, settings.calendly_event_type_uri)


__all__ = [
    "CalendlyClient",
    "CalendlyLink",
    "MockCalendlyClient",
    "RealCalendlyClient",
    "make_calendly_client",
]
