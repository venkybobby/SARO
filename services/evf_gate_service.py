"""
EVF Sprint 1 — Validation Gate service (FR-EVF-08).

The gate has 7 boolean items. All must be True before:
  - the gate can be locked
  - a QCO can be published for this engagement (enforced in Sprint 2)

Once locked, no further edits to gate items are permitted (409 on PATCH).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import ValidationGate

# The 7 gate item field names (FR-EVF-08)
GATE_ITEMS = (
    "coi_declared_approved",
    "sow_executed",
    "evidence_package_delivered",
    "product_demo_completed",
    "draft_qco_received",
    "saro_legal_review_completed",
    "qco_approved_ref_assigned",
)

# Evidence reference fields paired with each gate item
_EVIDENCE_FIELDS: dict[str, str] = {
    "coi_declared_approved":      "coi_evidence_ref",
    "sow_executed":                "sow_evidence_ref",
    "evidence_package_delivered":  "evidence_package_ref",
    "product_demo_completed":      "product_demo_ref",
    "draft_qco_received":          "draft_qco_ref",
    "saro_legal_review_completed": "legal_signoff_ref",
    "qco_approved_ref_assigned":   "qco_ref",
}


def get_gate(db: Session, engagement_id: uuid.UUID) -> ValidationGate:
    gate = (
        db.query(ValidationGate)
        .filter(ValidationGate.engagement_id == engagement_id)
        .first()
    )
    if gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation gate not found for this engagement")
    return gate


def update_gate(
    db: Session,
    engagement_id: uuid.UUID,
    *,
    updates: dict[str, Any],
) -> ValidationGate:
    gate = get_gate(db, engagement_id)
    if gate.locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Validation gate is locked — no further edits permitted. All 7 gate items were marked complete.",
        )

    allowed_fields = set(GATE_ITEMS) | set(_EVIDENCE_FIELDS.values())
    unknown = set(updates.keys()) - allowed_fields
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown gate fields: {sorted(unknown)}. Allowed: {sorted(allowed_fields)}",
        )

    for field, value in updates.items():
        setattr(gate, field, value)

    gate.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(gate)
    return gate


def lock_gate(
    db: Session,
    engagement_id: uuid.UUID,
    *,
    locked_by_user_id: uuid.UUID,
) -> ValidationGate:
    gate = get_gate(db, engagement_id)
    if gate.locked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Gate is already locked")

    incomplete = [item for item in GATE_ITEMS if not getattr(gate, item)]
    if incomplete:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot lock gate — the following items are not yet complete: {incomplete}",
        )

    gate.locked = True
    gate.locked_at = datetime.now(timezone.utc)
    gate.locked_by_user_id = locked_by_user_id
    gate.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(gate)
    return gate


def gate_is_locked(db: Session, engagement_id: uuid.UUID) -> bool:
    """Utility used by Sprint 2 QCO publish to enforce the gate requirement."""
    gate = (
        db.query(ValidationGate)
        .filter(ValidationGate.engagement_id == engagement_id)
        .first()
    )
    return gate is not None and gate.locked
