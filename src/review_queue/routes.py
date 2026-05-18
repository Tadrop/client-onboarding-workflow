"""AM review queue HTTP routes.

Endpoints:

  GET  /reviews                       list pending reviews
  GET  /reviews/{review_id}           one review + the draft it points at
  POST /reviews/{review_id}/approve   mark approved, advance the run
  POST /reviews/{review_id}/reject    mark rejected, milestone → failed
  GET  /runs                          list runs (for an AM dashboard)
  GET  /runs/{run_id}                 one run (with all milestones + drafts)
  POST /runs/{run_id}/resume          re-tick a run (e.g. after the degrade window)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, EmailStr

from ..logging_setup import get_logger
from ..milestones.orchestrator import (
    approve_and_continue,
    reject_and_retry,
    resume_run,
)
from ..schemas import AMReview, Draft, OnboardingRun, ReviewDecision
from ..state import get_store

router = APIRouter(tags=["review"])
log = get_logger(__name__)


class ReviewDetail(BaseModel):
    review: AMReview
    draft: Draft | None = None


class ApproveRequest(BaseModel):
    reviewer_email: EmailStr | None = None
    notes: str | None = None


class RejectRequest(BaseModel):
    reviewer_email: EmailStr | None = None
    notes: str


@router.get("/reviews", response_model=list[AMReview])
def list_pending() -> list[AMReview]:
    return get_store().list_pending_reviews()


@router.get("/reviews/{review_id}", response_model=ReviewDetail)
def get_review(review_id: str) -> ReviewDetail:
    store = get_store()
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review not found")
    return ReviewDetail(review=review, draft=store.get_draft(review.draft_id))


_EMPTY_APPROVE = ApproveRequest()


@router.post("/reviews/{review_id}/approve", response_model=ReviewDetail)
def approve(
    review_id: str,
    body: ApproveRequest = Body(default=_EMPTY_APPROVE),  # noqa: B008  (FastAPI pattern)
) -> ReviewDetail:
    store = get_store()
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review not found")
    if review.decision is not ReviewDecision.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"already decided: {review.decision.value}")

    review.decision = ReviewDecision.APPROVED
    review.reviewer_email = body.reviewer_email
    review.notes = body.notes
    review.decided_at = datetime.now(timezone.utc)
    store.save_review(review)

    approve_and_continue(review.run_id, review.milestone)
    return ReviewDetail(review=review, draft=store.get_draft(review.draft_id))


@router.post("/reviews/{review_id}/reject", response_model=ReviewDetail)
def reject(review_id: str, body: RejectRequest) -> ReviewDetail:
    store = get_store()
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "review not found")
    if review.decision is not ReviewDecision.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"already decided: {review.decision.value}")

    review.decision = ReviewDecision.REJECTED
    review.reviewer_email = body.reviewer_email
    review.notes = body.notes
    review.decided_at = datetime.now(timezone.utc)
    store.save_review(review)

    reject_and_retry(review.run_id, review.milestone)
    return ReviewDetail(review=review, draft=store.get_draft(review.draft_id))


@router.get("/runs", response_model=list[OnboardingRun])
def list_runs() -> list[OnboardingRun]:
    return get_store().list_runs()


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    store = get_store()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return {
        "run": run.model_dump(mode="json"),
        "drafts": [d.model_dump(mode="json") for d in store.drafts_for_run(run_id)],
        "reviews": [r.model_dump(mode="json") for r in store.reviews_for_run(run_id)],
    }


@router.post("/runs/{run_id}/resume", response_model=OnboardingRun)
def resume(run_id: str) -> OnboardingRun:
    try:
        return resume_run(run_id)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
