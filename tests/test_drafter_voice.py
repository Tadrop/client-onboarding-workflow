"""Drafter offline-fallback voice checks. (Hard guarantees, not vibe checks.)"""

from __future__ import annotations

from src.drafter.brief import draft_brief
from src.drafter.reminder import draft_reminder
from src.drafter.welcome import draft_welcome_email

from .fixtures.contracts import new_contract


def test_welcome_draft_contains_both_links() -> None:
    contract = new_contract()
    draft = draft_welcome_email(
        run_id="run_test",
        contract=contract,
        questionnaire_url="https://example.com/q",
        calendly_url="https://example.com/c",
    )
    assert "https://example.com/q" in draft.body
    assert "https://example.com/c" in draft.body
    assert "— The Halo team" in draft.body


def test_brief_degrade_mode_never_invents() -> None:
    contract = new_contract()
    draft = draft_brief(run_id="run_test", contract=contract, answers=None)
    # The hard contract: degrade mode MUST include placeholders, not fabrications.
    assert "[AM TO FILL:" in draft.body
    assert draft.metadata["mode"] == "am_fill_in"


def test_brief_from_answers_uses_provided_text() -> None:
    contract = new_contract()
    draft = draft_brief(
        run_id="run_test",
        contract=contract,
        answers={
            "objective": "Cut onboarding time by half",
            "audience": "AMs",
            "kpi": "Cycle time",
        },
    )
    assert "Cut onboarding time by half" in draft.body
    assert draft.metadata["mode"] == "from_answers"


def test_reminder_lists_missing_items() -> None:
    contract = new_contract()
    draft = draft_reminder(
        run_id="run_test", contract=contract, missing_items=["brand assets", "logo files"]
    )
    assert "brand assets" in draft.body or "brand assets, logo files" in draft.body
