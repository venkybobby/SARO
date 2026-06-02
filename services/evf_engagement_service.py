"""
EVF Sprint 1 — SME Engagement state machine service (FR-EVF-05).

Allowed transitions (one-way, no skipping):
  SHORTLISTED       → COI_CLEARED
  COI_CLEARED       → SOW_ISSUED
  SOW_ISSUED        → REVIEW_IN_PROGRESS
  REVIEW_IN_PROGRESS → DRAFT_QCO_RECEIVED
  DRAFT_QCO_RECEIVED → QCO_APPROVED
  QCO_APPROVED      → PUBLISHED
  PUBLISHED         → RENEWAL_TRIGGERED
  Any state         → RENEWAL_TRIGGERED  (early renewal allowed from any active state)

Hash chain: each transition row carries event_hash = SHA-256(payload + prev_hash)
so tampering with any historical row breaks all subsequent hashes.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import SMEEngagement, SMEEngagementState, SMEEngagementTransition, ValidationGate

# ── Allowed transitions ────────────────────────────────────────────────────────

_FORWARD = {
    SMEEngagementState.SHORTLISTED:        SMEEngagementState.COI_CLEARED,
    SMEEngagementState.COI_CLEARED:        SMEEngagementState.SOW_ISSUED,
    SMEEngagementState.SOW_ISSUED:         SMEEngagementState.REVIEW_IN_PROGRESS,
    SMEEngagementState.REVIEW_IN_PROGRESS: SMEEngagementState.DRAFT_QCO_RECEIVED,
    SMEEngagementState.DRAFT_QCO_RECEIVED: SMEEngagementState.QCO_APPROVED,
    SMEEngagementState.QCO_APPROVED:       SMEEngagementState.PUBLISHED,
    SMEEngagementState.PUBLISHED:          SMEEngagementState.RENEWAL_TRIGGERED,
}

# RENEWAL_TRIGGERED is reachable from any state as an emergency/early trigger
_ALWAYS_ALLOWED_TARGET = SMEEngagementState.RENEWAL_TRIGGERED


def _allowed_transitions(from_state: SMEEngagementState) -> set[SMEEngagementState]:
    targets = set()
    if fwd := _FORWARD.get(from_state):
        targets.add(fwd)
    if from_state is not SMEEngagementState.RENEWAL_TRIGGERED:
        targets.add(_ALWAYS_ALLOWED_TARGET)
    return targets


# ── Hash chain helpers ─────────────────────────────────────────────────────────

def _normalise_dt(value: object) -> str:
    """Return a stable UTC ISO string regardless of whether tz info survived a DB round-trip."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _build_transition_payload(transition: dict) -> dict:
    return {
        "id":            str(transition.get("id", "")),
        "engagement_id": str(transition.get("engagement_id", "")),
        "from_state":    str(transition.get("from_state", "")),
        "to_state":      str(transition.get("to_state", "")),
        "actor_user_id": str(transition.get("actor_user_id") or ""),
        "reason":        str(transition.get("reason") or ""),
        "created_at":    _normalise_dt(transition.get("created_at", "")),
    }


def _compute_transition_hash(transition: dict, prev_hash: Optional[str]) -> str:
    payload = _build_transition_payload(transition)
    payload["prev_hash"] = prev_hash or "GENESIS"
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# ── CRUD helpers ───────────────────────────────────────────────────────────────

def create_engagement(
    db: Session,
    *,
    sme_firm_name: str,
    framework: str,
    created_by_user_id: uuid.UUID,
    sme_key_contact: Optional[str] = None,
    sme_credential: Optional[str] = None,
    notes: Optional[str] = None,
) -> SMEEngagement:
    engagement = SMEEngagement(
        sme_firm_name=sme_firm_name,
        framework=framework,
        state=SMEEngagementState.SHORTLISTED.value,
        state_entered_at=datetime.now(timezone.utc),
        created_by_user_id=created_by_user_id,
        sme_key_contact=sme_key_contact,
        sme_credential=sme_credential,
        notes=notes,
    )
    db.add(engagement)
    db.flush()  # get id before writing gate + transition

    # Auto-create the ValidationGate so it's always available
    gate = ValidationGate(engagement_id=engagement.id)
    db.add(gate)

    # Genesis transition (SHORTLISTED is the initial state — no from_state)
    _write_transition(db, engagement=engagement, from_state="GENESIS", to_state=SMEEngagementState.SHORTLISTED.value, actor_user_id=created_by_user_id, reason="Engagement created")

    db.commit()
    db.refresh(engagement)
    return engagement


def get_engagement(db: Session, engagement_id: uuid.UUID) -> SMEEngagement:
    eng = db.get(SMEEngagement, engagement_id)
    if eng is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    return eng


def list_engagements(
    db: Session,
    *,
    framework: Optional[str] = None,
    state: Optional[str] = None,
) -> list[SMEEngagement]:
    q = db.query(SMEEngagement)
    if framework:
        q = q.filter(SMEEngagement.framework == framework)
    if state:
        q = q.filter(SMEEngagement.state == state)
    return q.order_by(SMEEngagement.created_at.desc()).all()


def transition_engagement(
    db: Session,
    engagement_id: uuid.UUID,
    *,
    to_state: str,
    actor_user_id: uuid.UUID,
    reason: Optional[str] = None,
) -> SMEEngagement:
    eng = get_engagement(db, engagement_id)
    from_enum = SMEEngagementState(eng.state)

    try:
        to_enum = SMEEngagementState(to_state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown state '{to_state}'. Valid states: {[s.value for s in SMEEngagementState]}",
        )

    allowed = _allowed_transitions(from_enum)
    if to_enum not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transition {from_enum.value} → {to_enum.value} is not permitted. "
                f"Allowed: {[s.value for s in allowed]}"
            ),
        )

    eng.state = to_enum.value
    eng.state_entered_at = datetime.now(timezone.utc)
    eng.updated_at = datetime.now(timezone.utc)

    _write_transition(
        db,
        engagement=eng,
        from_state=from_enum.value,
        to_state=to_enum.value,
        actor_user_id=actor_user_id,
        reason=reason,
    )

    db.commit()
    db.refresh(eng)
    return eng


def list_transitions(db: Session, engagement_id: uuid.UUID) -> list[SMEEngagementTransition]:
    get_engagement(db, engagement_id)  # 404 if missing
    return (
        db.query(SMEEngagementTransition)
        .filter(SMEEngagementTransition.engagement_id == engagement_id)
        .order_by(SMEEngagementTransition.created_at.asc())
        .all()
    )


def _write_transition(
    db: Session,
    *,
    engagement: SMEEngagement,
    from_state: str,
    to_state: str,
    actor_user_id: Optional[uuid.UUID],
    reason: Optional[str],
) -> SMEEngagementTransition:
    # Find the most recent transition hash for this engagement (chain head)
    prev = (
        db.query(SMEEngagementTransition)
        .filter(SMEEngagementTransition.engagement_id == engagement.id)
        .order_by(SMEEngagementTransition.created_at.desc())
        .first()
    )
    prev_hash = prev.event_hash if prev else None

    now = datetime.now(timezone.utc)
    t_id = uuid.uuid4()
    payload_data = {
        "id":            str(t_id),
        "engagement_id": str(engagement.id),
        "from_state":    from_state,
        "to_state":      to_state,
        "actor_user_id": str(actor_user_id) if actor_user_id else "",
        "reason":        reason or "",
        "created_at":    now.isoformat(),
    }
    event_hash = _compute_transition_hash(payload_data, prev_hash)

    t = SMEEngagementTransition(
        id=t_id,
        engagement_id=engagement.id,
        from_state=from_state,
        to_state=to_state,
        actor_user_id=actor_user_id,
        reason=reason,
        prev_hash=prev_hash,
        event_hash=event_hash,
        created_at=now,
    )
    db.add(t)
    return t
