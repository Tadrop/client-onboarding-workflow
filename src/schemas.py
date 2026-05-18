"""Pydantic schemas for the onboarding domain.

These are the durable types: anything written to the state store or crossing
a milestone boundary is one of these.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# ─── Enums ───────────────────────────────────────────────────────────────────


class ContractType(str, Enum):
    NEW = "new"
    RENEWAL = "renewal"


class ServiceType(str, Enum):
    BRANDING = "branding"
    WEB = "web"
    CAMPAIGN = "campaign"
    RETAINER = "retainer"


class EsignProvider(str, Enum):
    DOCUSIGN = "docusign"
    PANDADOC = "pandadoc"


class MilestoneName(str, Enum):
    WELCOME = "welcome"
    INTERNAL_SETUP = "internal_setup"
    KICKOFF = "kickoff"
    BRIEF = "brief"
    REMINDER = "reminder"
    RENEWAL_REFRESH = "renewal_refresh"


class MilestoneState(str, Enum):
    READY = "ready"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReviewDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ─── Core domain ─────────────────────────────────────────────────────────────


class ClientContact(BaseModel):
    name: str
    email: EmailStr
    role: str | None = None


class Contract(BaseModel):
    """The contract data extracted from an e-sign webhook payload."""

    provider: EsignProvider
    envelope_id: str
    contract_type: ContractType
    service_type: ServiceType
    client_name: str
    client_contacts: list[ClientContact] = Field(default_factory=list)
    existing_client_id: str | None = None
    envelope_subject: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    signed_at: datetime = Field(default_factory=_utcnow)


class Milestone(BaseModel):
    name: MilestoneName
    state: MilestoneState = MilestoneState.READY
    attempts: int = 0
    last_error: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utcnow)

    def transition(self, new_state: MilestoneState) -> None:
        self.state = new_state
        self.updated_at = _utcnow()


class OnboardingRun(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    run_id: str = Field(default_factory=lambda: _new_id("run"))
    contract: Contract
    milestones: dict[MilestoneName, Milestone] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)

    def get(self, name: MilestoneName) -> Milestone:
        return self.milestones[name]

    def all_done(self) -> bool:
        return all(
            m.state in (MilestoneState.DONE, MilestoneState.SKIPPED)
            for m in self.milestones.values()
        )


class DraftKind(str, Enum):
    WELCOME_EMAIL = "welcome_email"
    KICKOFF_INVITE = "kickoff_invite"
    BRIEF = "brief"
    REMINDER = "reminder"


class Draft(BaseModel):
    """A piece of external-client comms that requires AM approval before send."""

    draft_id: str = Field(default_factory=lambda: _new_id("draft"))
    run_id: str
    milestone: MilestoneName
    kind: DraftKind
    subject: str | None = None
    body: str
    recipients: list[EmailStr] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class AMReview(BaseModel):
    review_id: str = Field(default_factory=lambda: _new_id("rev"))
    run_id: str
    milestone: MilestoneName
    draft_id: str
    decision: ReviewDecision = ReviewDecision.PENDING
    reviewer_email: str | None = None
    notes: str | None = None
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class IdempotencyRecord(BaseModel):
    """Cache of (run_id, milestone, step) → result for safe re-runs."""

    key: str
    run_id: str
    milestone: MilestoneName
    step: str
    result: dict[str, Any]
    created_at: datetime = Field(default_factory=_utcnow)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def milestones_for(contract_type: ContractType) -> list[MilestoneName]:
    """The full milestone sequence for a contract type.

    Renewal flow is intentionally short — no welcome, no kickoff.
    """
    if contract_type is ContractType.RENEWAL:
        return [MilestoneName.RENEWAL_REFRESH]
    return [
        MilestoneName.WELCOME,
        MilestoneName.INTERNAL_SETUP,
        MilestoneName.KICKOFF,
        MilestoneName.BRIEF,
        MilestoneName.REMINDER,
    ]
