"""Drafter — Claude-backed copywriting in Halo's voice.

Three artifacts are drafted here:

  - the welcome email (with questionnaire + Calendly links)
  - the project brief (from questionnaire answers OR AM-fill-in template)
  - the polite checklist reminder (when assets are missing T+3d)

Every artifact is a `Draft` — never auto-sent. AM approval is the only trigger.
"""

from .brief import draft_brief
from .reminder import draft_reminder
from .welcome import draft_welcome_email

__all__ = ["draft_welcome_email", "draft_brief", "draft_reminder"]
