"""Draft the project brief.

Two modes:

  - `from_answers`: client filled the questionnaire, we have real answers.
  - `am_fill_in`: it's been 3+ days with no questionnaire response. We
    generate a brief with `[AM TO FILL: …]` placeholders. The drafter MUST
    NOT invent answers (CLAUDE.md §9 degrade rule).
"""

from __future__ import annotations

from ..schemas import Contract, Draft, DraftKind, MilestoneName
from .claude_client import complete
from .voice import HALO_VOICE


def draft_brief(
    *,
    run_id: str,
    contract: Contract,
    answers: dict[str, str] | None,
) -> Draft:
    am_fill_in = not answers
    system = (
        f"{HALO_VOICE}\n\n"
        "You are drafting a PROJECT BRIEF for the Halo team's internal review. "
        "Structure: 5 numbered sections — (1) The work, (2) Who we're talking "
        "to, (3) What success looks like, (4) Constraints and context, "
        "(5) Decision-makers. Use the answers below; if an answer is missing, "
        "insert a `[AM TO FILL: …]` placeholder describing what's needed. "
        "Never invent answers — placeholders only."
    )
    answer_lines = _format_answers(contract, answers)
    user = (
        f"client_name: {contract.client_name}\n"
        f"service_type: {contract.service_type.value}\n"
        f"{answer_lines}"
    )
    text = complete(system, user, max_tokens=1200)
    return Draft(
        run_id=run_id,
        milestone=MilestoneName.BRIEF,
        kind=DraftKind.BRIEF,
        subject=f"Project brief — {contract.client_name}",
        body=text,
        recipients=[],  # brief stays internal; AM shares manually
        metadata={
            "mode": "am_fill_in" if am_fill_in else "from_answers",
            "answer_count": len(answers or {}),
        },
    )


def _format_answers(contract: Contract, answers: dict[str, str] | None) -> str:
    if not answers:
        return (
            "objective: \n"
            "audience: \n"
            "kpi: \n"
            "_note: questionnaire not returned within degrade window — generate "
            "with [AM TO FILL: ...] placeholders only.\n"
        )
    lines = [f"{k}: {v}" for k, v in answers.items()]
    return "\n".join(lines) + "\n"
