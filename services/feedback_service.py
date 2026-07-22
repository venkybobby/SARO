"""Pilot feedback intake + triage (STORY-382).

A feedback form is the one place in SARO where free text is a feature, not a
leak vector — so INV-2 is handled by mitigation, stated honestly:

* A visible **"do not include patient information"** notice, exposed in the API
  contract (:data:`NO_PHI_NOTICE`) so the widget renders it and a submitter is
  warned before typing.
* A server-side **length cap** (the model's ``body`` column plus
  :data:`MAX_BODY_CHARS`), so an accidental paste of a large record is refused.
* The table is **excluded from evidence exports** — a pilot's "this screen is
  confusing" note must never surface in an auditor's evidence pack.

Categories, severities, and triage states are closed vocabularies; the free-text
``body`` is the only open field, and it is capped.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

NO_PHI_NOTICE = (
    "Do not include patient information or any protected health information (PHI) "
    "in this feedback. Describe the issue in general terms."
)

MAX_BODY_CHARS = 4000

CATEGORIES = frozenset({"bug", "gap", "confusing", "feature"})
SEVERITIES = frozenset({"low", "medium", "high"})
# Triage lifecycle. A terminal state (declined/parked) or a link (story_linked)
# closes the loop; every item must reach one of these in the weekly ritual.
TRIAGE_STATES = frozenset({"new", "triaged", "story_linked", "declined", "parked"})


class FeedbackError(ValueError):
    """Invalid feedback submission."""


def submit(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    screen: str,
    category: str,
    severity: str,
    body: str,
    user_id: Optional[uuid.UUID] = None,
) -> Any:
    """Record one feedback item. Validates the closed vocabularies + length cap."""
    from models import PilotFeedback

    if category not in CATEGORIES:
        raise FeedbackError(f"unknown category {category!r} (allowed: {sorted(CATEGORIES)})")
    if severity not in SEVERITIES:
        raise FeedbackError(f"unknown severity {severity!r} (allowed: {sorted(SEVERITIES)})")
    body = (body or "").strip()
    if not body:
        raise FeedbackError("feedback body is empty")
    if len(body) > MAX_BODY_CHARS:
        raise FeedbackError(
            f"feedback body exceeds {MAX_BODY_CHARS} chars — trim it; large pastes "
            "risk including record content the form must not carry"
        )

    item = PilotFeedback(
        tenant_id=tenant_id,
        user_id=user_id,
        screen=str(screen)[:64],
        category=category,
        severity=severity,
        body=body,
        triage_status="new",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def triage(
    db: Session,
    *,
    feedback_id: uuid.UUID,
    status: str,
    story_id: Optional[str] = None,
    note: Optional[str] = None,
) -> Any:
    """Move a feedback item along its triage lifecycle."""
    from models import PilotFeedback

    if status not in TRIAGE_STATES:
        raise FeedbackError(f"unknown triage status {status!r} (allowed: {sorted(TRIAGE_STATES)})")
    if status == "story_linked" and not story_id:
        raise FeedbackError("story_linked requires a story_id")
    if status == "declined" and not note:
        raise FeedbackError("declined requires a reason in the note")

    item = db.get(PilotFeedback, feedback_id)
    if item is None:
        raise FeedbackError(f"feedback {feedback_id} not found")
    item.triage_status = status
    item.story_id = story_id
    item.triage_note = note
    db.commit()
    db.refresh(item)
    return item


def list_for_triage(db: Session, *, status: Optional[str] = None) -> list[Any]:
    """Internal triage view: all feedback (optionally filtered by status)."""
    from models import PilotFeedback

    q = db.query(PilotFeedback)
    if status is not None:
        q = q.filter(PilotFeedback.triage_status == status)
    return q.order_by(PilotFeedback.created_at.desc()).all()
