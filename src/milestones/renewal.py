"""Milestone R1 — Renewal refresh.

Renewal-only path. Strictly NO welcome email, NO kickoff call. The renewal
flow refreshes existing infrastructure:

  - Update ClickUp dates on the existing project (or create a new project if
    none exists in the artifact — we don't have a real lookup in mock mode)
  - Refresh the Drive folder
  - Post a notification in the existing Slack channel (or create a new one)

`renewal_safety` test guarantees this milestone NEVER emits a welcome email.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..integrations import IntegrationBundle
from ..logging_setup import get_logger
from ..schemas import MilestoneName, MilestoneState, OnboardingRun
from ..state import Store
from ..state.idempotency import run_idempotent
from ..state.transitions import transition

log = get_logger(__name__)


def run(run: OnboardingRun, store: Store, clients: IntegrationBundle) -> None:
    transition(store, run, MilestoneName.RENEWAL_REFRESH, MilestoneState.RUNNING)

    clickup_artifact = run_idempotent(
        store,
        run.run_id,
        MilestoneName.RENEWAL_REFRESH,
        "clickup_refresh",
        lambda: _refresh_clickup(clients, run),
    )
    drive_artifact = run_idempotent(
        store,
        run.run_id,
        MilestoneName.RENEWAL_REFRESH,
        "drive_refresh",
        lambda: _refresh_drive(clients, run),
    )
    slack_artifact = run_idempotent(
        store,
        run.run_id,
        MilestoneName.RENEWAL_REFRESH,
        "slack_notify",
        lambda: _slack_notify(clients, run),
    )

    transition(
        store,
        run,
        MilestoneName.RENEWAL_REFRESH,
        MilestoneState.DONE,
        artifacts={
            "clickup": clickup_artifact,
            "drive": drive_artifact,
            "slack": slack_artifact,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _refresh_clickup(clients: IntegrationBundle, run: OnboardingRun) -> dict:
    project = clients.clickup.create_project(
        run.contract.client_name, run.contract.service_type.value
    )
    clients.clickup.update_project_dates(
        project.id, retainer_start=run.contract.signed_at.isoformat()
    )
    return {"project_id": project.id, "project_name": project.name}


def _refresh_drive(clients: IntegrationBundle, run: OnboardingRun) -> dict:
    folder = clients.drive.create_client_folder(
        run.contract.client_name, run.contract.service_type.value
    )
    clients.drive.refresh(folder.id)
    return {"folder_id": folder.id, "folder_name": folder.name}


def _slack_notify(clients: IntegrationBundle, run: OnboardingRun) -> dict:
    name = clients.slack.channel_name(run.contract.client_name, run.contract.service_type.value)
    channel = clients.slack.create_channel(name)
    clients.slack.post_message(
        channel.id, f"Retainer renewed for {run.contract.client_name} — refreshed setup."
    )
    return {"channel_id": channel.id, "channel_name": channel.name}
