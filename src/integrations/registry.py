"""Bundle of integration clients for one onboarding run.

Tests can swap out individual clients via `IntegrationBundle.override()`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from .calendly import CalendlyClient, make_calendly_client
from .clickup import ClickUpClient, make_clickup_client
from .drive import DriveClient, make_drive_client
from .slack import SlackClient, make_slack_client
from .typeform import TypeformClient, make_typeform_client


@dataclass(frozen=True)
class IntegrationBundle:
    slack: SlackClient
    clickup: ClickUpClient
    drive: DriveClient
    calendly: CalendlyClient
    typeform: TypeformClient

    def override(self, **kwargs: object) -> IntegrationBundle:
        return replace(self, **kwargs)  # type: ignore[arg-type]


@lru_cache(maxsize=1)
def get_clients() -> IntegrationBundle:
    return IntegrationBundle(
        slack=make_slack_client(),
        clickup=make_clickup_client(),
        drive=make_drive_client(),
        calendly=make_calendly_client(),
        typeform=make_typeform_client(),
    )


def reset_clients_cache() -> None:
    get_clients.cache_clear()
