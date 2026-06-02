"""
EVF Sprint 2 — Publication audit trail service (FR-EVF-20, FR-EVF-21).

Every external publication of a compliance claim must be logged here with
five required fields (AC-21a):
  1. timestamp             — UTC, server-set, immutable
  2. artefact_identifier   — report_id / scan_id / dashboard widget / deck ref
  3. qco_reference_number  — FK soft-ref to QCORegistry
  4. publisher_user_id     — identity of the publishing user
  5. distribution_channel  — one of EVFDistributionChannel enum values

Hash chain: event_hash = SHA-256(payload + prev_hash) so any modification
to a historical record breaks all downstream hashes (AC-21b).

The chain head is the most recent event ordered by timestamp ASC, id ASC.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import QCOPublicationEvent, QCORegistry

# ── Hash chain helpers ────────────────────────────────────────────────────────

_PUBLICATION_CHAIN_GENESIS = "GENESIS"


def _build_publication_payload(data: dict) -> dict:
    """Canonical hash payload — must match exactly between write and verify paths."""
    return {
        "id":                   str(data.get("id", "")),
        "qco_reference_number": str(data.get("qco_reference_number", "")),
        "artefact_identifier":  str(data.get("artefact_identifier", "")),
        "publisher_user_id":    str(data.get("publisher_user_id", "")),
        "distribution_channel": str(data.get("distribution_channel", "")),
        "timestamp":            str(data.get("timestamp", "")),
    }


def compute_publication_hash(data: dict, prev_hash: Optional[str]) -> str:
    payload = _build_publication_payload(data)
    payload["prev_hash"] = prev_hash or _PUBLICATION_CHAIN_GENESIS
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def get_publication_chain_head(db: Session) -> Optional[str]:
    """Return event_hash of the most recent publication event (chain head)."""
    latest = (
        db.query(QCOPublicationEvent)
        .order_by(QCOPublicationEvent.timestamp.asc(), QCOPublicationEvent.id.asc())
        .all()
    )
    return latest[-1].event_hash if latest else None


# ── Write ─────────────────────────────────────────────────────────────────────

def record_publication_event(
    db: Session,
    *,
    qco_reference_number: str,
    artefact_identifier: str,
    publisher_user_id: uuid.UUID,
    distribution_channel: str,
    idempotency_key: Optional[str] = None,
) -> QCOPublicationEvent:
    """
    Write one publication event. Idempotent when idempotency_key is provided —
    returns the existing event rather than creating a duplicate (AC-21b / retry safety).
    """
    # Idempotency check
    if idempotency_key:
        existing = (
            db.query(QCOPublicationEvent)
            .filter(QCOPublicationEvent.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

    # Validate QCO reference exists
    qco_exists = (
        db.query(QCORegistry)
        .filter(QCORegistry.qco_reference_number == qco_reference_number)
        .first()
    )
    if qco_exists is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"QCO reference '{qco_reference_number}' not found in registry.",
        )

    prev_hash = get_publication_chain_head(db)
    now = datetime.now(timezone.utc)
    event_id = uuid.uuid4()

    event_hash = compute_publication_hash(
        {
            "id":                   str(event_id),
            "qco_reference_number": qco_reference_number,
            "artefact_identifier":  artefact_identifier,
            "publisher_user_id":    str(publisher_user_id),
            "distribution_channel": distribution_channel,
            "timestamp":            now.isoformat(),
        },
        prev_hash,
    )

    event = QCOPublicationEvent(
        id=event_id,
        qco_reference_number=qco_reference_number,
        artefact_identifier=artefact_identifier,
        publisher_user_id=publisher_user_id,
        distribution_channel=distribution_channel,
        timestamp=now,
        prev_hash=prev_hash,
        event_hash=event_hash,
        idempotency_key=idempotency_key,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ── Read / verify ─────────────────────────────────────────────────────────────

def list_publication_events(
    db: Session,
    *,
    qco_reference_number: Optional[str] = None,
    distribution_channel: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[QCOPublicationEvent]:
    q = (
        db.query(QCOPublicationEvent)
        .order_by(QCOPublicationEvent.timestamp.asc(), QCOPublicationEvent.id.asc())
    )
    if qco_reference_number:
        q = q.filter(QCOPublicationEvent.qco_reference_number == qco_reference_number)
    if distribution_channel:
        q = q.filter(QCOPublicationEvent.distribution_channel == distribution_channel)
    return q.offset(offset).limit(limit).all()


def verify_publication_chain(db: Session) -> dict:
    """
    Walk the entire publication event chain in order and verify each hash.
    Returns a result dict matching the audit_chain verify-chain response shape
    for consistency with the existing /api/v1/audit/verify-chain endpoint.
    """
    events = (
        db.query(QCOPublicationEvent)
        .order_by(QCOPublicationEvent.timestamp.asc(), QCOPublicationEvent.id.asc())
        .all()
    )

    if not events:
        return {
            "valid": True,
            "events_checked": 0,
            "chain": "evf_publications",
            "last_verified": datetime.now(timezone.utc).isoformat(),
            "break_at_event_id": None,
            "expected_hash": None,
            "actual_hash": None,
        }

    prev_hash: Optional[str] = None
    for i, event in enumerate(events):
        expected = compute_publication_hash(
            {
                "id":                   str(event.id),
                "qco_reference_number": event.qco_reference_number,
                "artefact_identifier":  event.artefact_identifier,
                "publisher_user_id":    str(event.publisher_user_id),
                "distribution_channel": event.distribution_channel,
                "timestamp":            (
                    event.timestamp.astimezone(timezone.utc).isoformat()
                    if event.timestamp.tzinfo
                    else event.timestamp.replace(tzinfo=timezone.utc).isoformat()
                ),
            },
            prev_hash,
        )
        if expected != event.event_hash:
            return {
                "valid": False,
                "events_checked": i,
                "chain": "evf_publications",
                "last_verified": datetime.now(timezone.utc).isoformat(),
                "break_at_event_id": str(event.id),
                "expected_hash": expected,
                "actual_hash": event.event_hash,
            }
        prev_hash = event.event_hash

    return {
        "valid": True,
        "events_checked": len(events),
        "chain": "evf_publications",
        "last_verified": datetime.now(timezone.utc).isoformat(),
        "break_at_event_id": None,
        "expected_hash": None,
        "actual_hash": None,
    }
