"""Offline fallbacks for Claude calls.

These run in CI / local dev / tests when no `ANTHROPIC_API_KEY` is set. They
must hit the same shape as the real Claude output: prose in Halo's voice
(or `[AM TO FILL: …]` placeholders for unknowns), no JSON, no markdown.
"""

from __future__ import annotations

from .claude_client import set_offline_fallback


def deterministic_fallback(system: str, user: str) -> str:
    """A predictable, voice-correct stand-in for the live Claude call.

    The system prompt routes us to one of three artifact templates. We keep
    the templates simple and AM-friendly: they can edit before sending.
    """
    s = system.lower()
    if "welcome email" in s:
        return _welcome_template(user)
    if "project brief" in s:
        return _brief_template(user)
    if "reminder" in s:
        return _reminder_template(user)
    return (
        "Hello,\n\n"
        "[AM TO FILL: this is a deterministic offline fallback. Set ANTHROPIC_API_KEY "
        "or register a richer fallback to replace this body.]\n\n"
        "— The Halo team"
    )


def _welcome_template(user: str) -> str:
    facts = _parse_facts(user)
    client = facts.get("client_name", "[AM TO FILL: client name]")
    questionnaire = facts.get("questionnaire_url", "[AM TO FILL: questionnaire link]")
    calendly = facts.get("calendly_url", "[AM TO FILL: kickoff scheduling link]")
    return (
        f"Subject: Welcome to Halo, {client}\n\n"
        f"Hi {client} team,\n\n"
        "We're glad you're here. Two quick things to get us moving:\n\n"
        f"  1. A short onboarding questionnaire — five minutes, mostly about the "
        f"shape of your business and what you want this engagement to do: "
        f"{questionnaire}\n"
        f"  2. A kickoff call so we can meet the team and put faces to names: "
        f"{calendly}\n\n"
        "If anything's blocking either of those, just reply to this email and "
        "we'll find another way.\n\n"
        "— The Halo team"
    )


def _brief_template(user: str) -> str:
    facts = _parse_facts(user)
    client = facts.get("client_name", "[AM TO FILL: client name]")
    service = facts.get("service_type", "[AM TO FILL: service type]")
    objective = facts.get("objective", "[AM TO FILL: primary objective]")
    audience = facts.get("audience", "[AM TO FILL: primary audience]")
    kpi = facts.get("kpi", "[AM TO FILL: success metric]")
    return (
        f"Project brief — {client} ({service})\n"
        "================================================\n\n"
        "1. The work\n"
        f"   {objective}\n\n"
        "2. Who we're talking to\n"
        f"   {audience}\n\n"
        "3. What success looks like\n"
        f"   {kpi}\n\n"
        "4. Constraints and context\n"
        "   [AM TO FILL: known constraints — timing, budget, legal, brand do/don't]\n\n"
        "5. Decision-makers\n"
        "   [AM TO FILL: who signs off each phase]\n\n"
        "— Drafted by Halo, ready for AM review"
    )


def _reminder_template(user: str) -> str:
    facts = _parse_facts(user)
    client = facts.get("client_name", "[AM TO FILL: client name]")
    missing = facts.get("missing", "a couple of items we're still waiting on")
    return (
        f"Subject: Quick nudge — {client} kickoff\n\n"
        f"Hi {client} team,\n\n"
        f"Just a friendly nudge: we're still missing {missing}. "
        "Once we've got those we can start the work properly.\n\n"
        "No rush — but a reply this week would keep us on schedule. If anything "
        "on the list is unclear, say so and we'll help.\n\n"
        "— The Halo team"
    )


def _parse_facts(user: str) -> dict[str, str]:
    """Extract `key: value` lines from the prompt — see drafter callers."""
    facts: dict[str, str] = {}
    for line in user.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            facts[k.strip().lower()] = v.strip()
    return facts


def install_default_offline_fallback() -> None:
    set_offline_fallback(deterministic_fallback)
