"""[DEGRADE] No questionnaire after 3 days → brief uses AM-fill-in mode, never invents."""

from __future__ import annotations

from datetime import timedelta

from src.milestones import brief as brief_module
from src.milestones.orchestrator import approve_and_continue, start_run
from src.schemas import MilestoneName, MilestoneState

from .fixtures.contracts import new_contract


def _advance_to_brief(store, clients):
    contract = new_contract()
    run = start_run(contract, store=store, clients=clients)
    # Approve welcome → flow advances through internal_setup → kickoff → brief.
    approve_and_continue(run.run_id, MilestoneName.WELCOME, store=store, clients=clients)
    return store.get_run(run.run_id)


def test_brief_waits_inside_degrade_window(store, clients, settings) -> None:
    run = _advance_to_brief(store, clients)
    # Inside the degrade window → brief should be `ready` (waiting).
    assert run.milestones[MilestoneName.BRIEF].state is MilestoneState.READY


def test_brief_degrades_to_am_fill_in_after_window(store, clients, settings) -> None:
    run = _advance_to_brief(store, clients)
    welcome = run.milestones[MilestoneName.WELCOME]
    now = welcome.updated_at + timedelta(days=settings.questionnaire_degrade_days + 1)
    brief_module.run(run, store, clients, now=now)

    fresh = store.get_run(run.run_id)
    b = fresh.milestones[MilestoneName.BRIEF]
    assert b.state is MilestoneState.AWAITING_APPROVAL
    assert b.artifacts["mode"] == "am_fill_in"

    draft = store.find_draft(run.run_id, MilestoneName.BRIEF)
    assert draft is not None
    # The hard rule: never invent answers — body MUST contain a placeholder.
    assert "[AM TO FILL:" in draft.body


def test_brief_uses_answers_when_questionnaire_returned(store, clients) -> None:
    run = _advance_to_brief(store, clients)
    form_id = run.milestones[MilestoneName.WELCOME].artifacts["questionnaire_form_id"]
    primary_email = run.contract.client_contacts[0].email
    clients.typeform.set_response(
        form_id,
        primary_email,
        {
            "objective": "Launch a refreshed brand in Q3",
            "audience": "Mid-market B2B finance teams",
            "kpi": "Pipeline-attributed revenue per quarter",
        },
    )
    brief_module.run(run, store, clients)
    fresh = store.get_run(run.run_id)
    assert fresh.milestones[MilestoneName.BRIEF].state is MilestoneState.AWAITING_APPROVAL
    assert fresh.milestones[MilestoneName.BRIEF].artifacts["mode"] == "from_answers"
    draft = store.find_draft(run.run_id, MilestoneName.BRIEF)
    assert draft is not None
    assert "Launch a refreshed brand in Q3" in draft.body
