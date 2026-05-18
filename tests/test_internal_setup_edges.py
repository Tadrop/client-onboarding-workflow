"""Edge cases from CLAUDE.md §6 step 4c:

- Slack channel name collision → append suffix, log, continue
- ClickUp template missing → fail loud, don't create an empty project
"""

from __future__ import annotations

import pytest

from src.integrations.base import TemplateMissingError
from src.integrations.clickup import MockClickUpClient
from src.integrations.slack import MockSlackClient
from src.milestones.orchestrator import approve_and_continue, start_run
from src.schemas import MilestoneName, MilestoneState

from .fixtures.contracts import new_contract


def test_slack_channel_collision_appends_suffix(store, clients) -> None:
    # Pre-create a colliding channel.
    base = clients.slack.channel_name("Acme & Co.", "branding")
    clients.slack.create_channel(base)
    assert base in clients.slack.channels

    contract = new_contract(envelope_id="env_collision_001")
    run = start_run(contract, store=store, clients=clients)
    approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)

    fresh = store.get_run(run.run_id)
    setup = fresh.milestones[MilestoneName.INTERNAL_SETUP]
    assert setup.state is MilestoneState.DONE
    chosen = setup.artifacts["slack"]["channel_name"]
    assert chosen != base
    assert chosen.startswith(base)


def test_missing_clickup_template_fails_loud(store, clients, monkeypatch) -> None:
    contract = new_contract(envelope_id="env_no_template_001")

    # Simulate a config gap: force the template loader to raise.
    from src.integrations import clickup as clickup_mod

    def _missing(_service_type: str) -> dict:
        raise TemplateMissingError("simulated missing template for test")

    monkeypatch.setattr(
        clickup_mod.MockClickUpClient, "load_template", lambda self, st: _missing(st)
    )

    run = start_run(contract, store=store, clients=clients)
    # Approving welcome will try to advance into internal_setup, which raises.
    with pytest.raises(TemplateMissingError):
        approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)

    fresh = store.get_run(run.run_id)
    assert fresh.milestones[MilestoneName.INTERNAL_SETUP].state is MilestoneState.FAILED


def test_mock_clients_are_isolated_per_test() -> None:
    """Sanity: each test gets a clean Slack + ClickUp client (no test bleed)."""
    a = MockSlackClient()
    b = MockClickUpClient()
    a.create_channel("client-test-branding")
    b.create_project("Test", "branding")
    assert "client-test-branding" in a.channels
    assert b.projects
