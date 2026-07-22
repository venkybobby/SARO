"""Pilot feedback API (STORY-382).

``GET /api/v1/feedback/form`` returns the form contract — the closed category
and severity vocabularies and the no-PHI notice — so the widget renders from the
contract rather than hardcoding it. ``POST`` submits; the triage view is
privileged (operator only).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import User
import services.feedback_service as feedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    screen: str = Field(..., max_length=64)
    category: str
    severity: str
    body: str = Field(..., min_length=1, max_length=feedback.MAX_BODY_CHARS)


def _serialize(item) -> dict:
    return {
        "id": str(item.id),
        "screen": item.screen,
        "category": item.category,
        "severity": item.severity,
        "body": item.body,
        "triage_status": item.triage_status,
        "story_id": item.story_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/form", summary="Feedback form contract (vocab + no-PHI notice)")
def form_contract(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    """The widget renders from this — categories, severities, and the notice it
    must display above the free-text field."""
    return {
        "categories": sorted(feedback.CATEGORIES),
        "severities": sorted(feedback.SEVERITIES),
        "max_body_chars": feedback.MAX_BODY_CHARS,
        "no_phi_notice": feedback.NO_PHI_NOTICE,
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Submit feedback")
def submit_feedback(
    payload: FeedbackIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    try:
        item = feedback.submit(
            db,
            tenant_id=current_user.tenant_id,
            user_id=getattr(current_user, "id", None),
            screen=payload.screen,
            category=payload.category,
            severity=payload.severity,
            body=payload.body,
        )
    except feedback.FeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _serialize(item)


@router.get(
    "/triage",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Internal triage view (operator only)",
)
def triage_view(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    triage_status: Optional[str] = None,
) -> dict:
    items = feedback.list_for_triage(db, status=triage_status)
    return {"count": len(items), "items": [_serialize(i) for i in items]}


class TriageIn(BaseModel):
    triage_status: str
    story_id: Optional[str] = None
    note: Optional[str] = None


@router.patch(
    "/{feedback_id}/triage",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Triage a feedback item (operator only)",
)
def triage_item(
    feedback_id: uuid.UUID,
    payload: TriageIn,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    try:
        item = feedback.triage(
            db,
            feedback_id=feedback_id,
            status=payload.triage_status,
            story_id=payload.story_id,
            note=payload.note,
        )
    except feedback.FeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _serialize(item)
