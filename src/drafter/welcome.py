"""Draft the welcome email — handed to AM for review before sending."""

from __future__ import annotations

from ..schemas import Contract, Draft, DraftKind, MilestoneName
from .claude_client import complete
from .voice import HALO_VOICE


def draft_welcome_email(
    *,
    run_id: str,
    contract: Contract,
    questionnaire_url: str,
    calendly_url: str,
) -> Draft:
    system = (
        f"{HALO_VOICE}\n\n"
        "You are drafting a WELCOME EMAIL for a new client. Include both the "
        "questionnaire link and the kickoff scheduling link. Keep it under 120 "
        "words. Output a subject line on the first line as `Subject: …`, then "
        "a blank line, then the body."
    )
    user = (
        f"client_name: {contract.client_name}\n"
        f"service_type: {contract.service_type.value}\n"
        f"questionnaire_url: {questionnaire_url}\n"
        f"calendly_url: {calendly_url}\n"
    )
    text = complete(system, user, max_tokens=800)
    subject, body = _split_subject(text)
    return Draft(
        run_id=run_id,
        milestone=MilestoneName.WELCOME,
        kind=DraftKind.WELCOME_EMAIL,
        subject=subject,
        body=body,
        recipients=[c.email for c in contract.client_contacts],
        metadata={
            "questionnaire_url": questionnaire_url,
            "calendly_url": calendly_url,
        },
    )


def _split_subject(text: str) -> tuple[str | None, str]:
    lines = text.lstrip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
        return subject, body
    return None, text
