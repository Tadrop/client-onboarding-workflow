"""Draft a polite checklist reminder for missing assets / info."""

from __future__ import annotations

from ..schemas import Contract, Draft, DraftKind, MilestoneName
from .claude_client import complete
from .voice import HALO_VOICE


def draft_reminder(
    *,
    run_id: str,
    contract: Contract,
    missing_items: list[str],
) -> Draft:
    system = (
        f"{HALO_VOICE}\n\n"
        "You are drafting a POLITE REMINDER email about missing onboarding "
        "items. Keep it short — under 100 words — and warm. List the missing "
        "items as a tidy bullet list. Output `Subject: …` on the first line, "
        "then a blank line, then the body."
    )
    missing = ", ".join(missing_items) if missing_items else "a couple of items"
    user = (
        f"client_name: {contract.client_name}\n"
        f"service_type: {contract.service_type.value}\n"
        f"missing: {missing}\n"
    )
    text = complete(system, user, max_tokens=600)
    subject, body = _split_subject(text)
    return Draft(
        run_id=run_id,
        milestone=MilestoneName.REMINDER,
        kind=DraftKind.REMINDER,
        subject=subject,
        body=body,
        recipients=[c.email for c in contract.client_contacts],
        metadata={"missing_items": missing_items},
    )


def _split_subject(text: str) -> tuple[str | None, str]:
    lines = text.lstrip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
        return subject, body
    return None, text
