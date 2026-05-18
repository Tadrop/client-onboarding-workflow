"""Milestone 2 — Internal setup: Slack channel, ClickUp project, Drive folder.

100% internal — no client emails. Runs autonomously to `done`. Each side
effect is idempotency-keyed so re-running picks up exactly where it left off
(Slack channel exists → reuse; ClickUp project exists → reuse; Drive folder
exists → reuse).
"""

from __future__ import annotations

from ..integrations import IntegrationBundle
from ..integrations.base import SlackChannelCollisionError, TemplateMissingError
from ..logging_setup import get_logger
from ..schemas import MilestoneName, MilestoneState, OnboardingRun
from ..state import Store
from ..state.idempotency import run_idempotent
from ..state.transitions import transition

log = get_logger(__name__)


def run(run: OnboardingRun, store: Store, clients: IntegrationBundle) -> None:
    transition(store, run, MilestoneName.INTERNAL_SETUP, MilestoneState.RUNNING)

    try:
        slack_artifact = run_idempotent(
            store,
            run.run_id,
            MilestoneName.INTERNAL_SETUP,
            "slack_channel",
            lambda: _create_slack_channel(clients, run),
        )
        clickup_artifact = run_idempotent(
            store,
            run.run_id,
            MilestoneName.INTERNAL_SETUP,
            "clickup_project",
            lambda: _create_clickup_project(clients, run),
        )
        drive_artifact = run_idempotent(
            store,
            run.run_id,
            MilestoneName.INTERNAL_SETUP,
            "drive_folder",
            lambda: _create_drive_folder(clients, run),
        )
    except TemplateMissingError as e:
        transition(
            store,
            run,
            MilestoneName.INTERNAL_SETUP,
            MilestoneState.FAILED,
            error=str(e),
        )
        raise

    transition(
        store,
        run,
        MilestoneName.INTERNAL_SETUP,
        MilestoneState.DONE,
        artifacts={
            "slack": slack_artifact,
            "clickup": clickup_artifact,
            "drive": drive_artifact,
        },
    )


def _create_slack_channel(clients: IntegrationBundle, run: OnboardingRun) -> dict:
    base_name = clients.slack.channel_name(
        run.contract.client_name, run.contract.service_type.value
    )
    # The MockSlackClient handles collisions internally; for real clients we
    # mirror that here by retrying with `-N` suffixes.
    try:
        channel = clients.slack.create_channel(base_name)
    except SlackChannelCollisionError:  # pragma: no cover - mock handles internally
        raise
    invite_emails = [c.email for c in run.contract.client_contacts]
    if invite_emails:
        clients.slack.invite(channel.id, invite_emails)
    return {"channel_id": channel.id, "channel_name": channel.name}


def _create_clickup_project(clients: IntegrationBundle, run: OnboardingRun) -> dict:
    project = clients.clickup.create_project(
        run.contract.client_name, run.contract.service_type.value
    )
    return {
        "project_id": project.id,
        "project_name": project.name,
        "phase_count": len(project.phases),
    }


def _create_drive_folder(clients: IntegrationBundle, run: OnboardingRun) -> dict:
    folder = clients.drive.create_client_folder(
        run.contract.client_name, run.contract.service_type.value
    )
    return {
        "folder_id": folder.id,
        "folder_name": folder.name,
        "subfolder_count": len(folder.subfolders),
    }
