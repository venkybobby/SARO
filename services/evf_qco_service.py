"""
EVF Sprint 2 — QCO Registry service (FR-EVF-10).

Responsibilities:
  - Reference number generation: SARO-QCO-{FRAMEWORK}-{YYYY}-{SEQ:03d}
  - Immutability enforcement: published QCOs raise QCOImmutableError on edit
  - 12-month expiry validation at publish time
  - Hash chain: each published QCO row carries prev_hash + record_hash covering
    the immutable fields so the registry itself is tamper-evident
  - Renewal: creates a new QCO record and sets superseded_by_qco_id on the old one

Hash payload fields (canonical, write-once):
  qco_reference_number, framework_covered, saro_version_assessed,
  sme_firm, sme_credential, issue_date, expiry_date,
  scope_boundary_summary, document_sha256, engagement_id,
  published_by_user_id, prev_hash
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import QCORegistry, QCOPublicationEvent
from services.evf_gate_service import gate_is_locked

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_VALIDITY_DAYS = 365  # FR-EVF-13: QCOs valid for maximum 12 months


class QCOImmutableError(HTTPException):
    """Raised when caller tries to modify a published (immutable) QCO."""

    def __init__(self, qco_ref: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"QCO '{qco_ref}' is published and immutable. "
                "Create a renewal instead of editing the published record."
            ),
        )


# ── Reference number generator ────────────────────────────────────────────────

def _next_sequence(db: Session, framework: str, year: int) -> int:
    """Return the next available sequence number for a framework+year pair."""
    prefix = f"SARO-QCO-{framework}-{year}-"
    count = (
        db.query(func.count(QCORegistry.id))
        .filter(QCORegistry.qco_reference_number.like(f"{prefix}%"))
        .scalar()
    ) or 0
    return count + 1


def generate_reference_number(db: Session, framework: str) -> str:
    """Generate a unique QCO reference number: SARO-QCO-{FRAMEWORK}-{YYYY}-{SEQ:03d}."""
    year = datetime.now(timezone.utc).year
    seq = _next_sequence(db, framework, year)
    return f"SARO-QCO-{framework}-{year}-{seq:03d}"


# ── Hash chain ────────────────────────────────────────────────────────────────

def _normalise_date(value: object) -> str:
    """Return a stable YYYY-MM-DD string regardless of whether value is date or datetime."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _build_qco_payload(qco: QCORegistry) -> dict:
    """Canonical hash payload — covers all immutable fields."""
    return {
        "id":                     str(qco.id),
        "qco_reference_number":   str(qco.qco_reference_number),
        "framework_covered":      str(qco.framework_covered),
        "saro_version_assessed":  str(qco.saro_version_assessed),
        "sme_firm":               str(qco.sme_firm),
        "sme_credential":         str(qco.sme_credential or ""),
        "issue_date":             _normalise_date(qco.issue_date),
        "expiry_date":            _normalise_date(qco.expiry_date),
        "scope_boundary_summary": str(qco.scope_boundary_summary or ""),
        "document_sha256":        str(qco.document_sha256 or ""),
        "engagement_id":          str(qco.engagement_id or ""),
        "published_by_user_id":   str(qco.published_by_user_id or ""),
    }


def _compute_record_hash(qco: QCORegistry, prev_hash: Optional[str]) -> str:
    payload = _build_qco_payload(qco)
    payload["prev_hash"] = prev_hash or "GENESIS"
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _get_registry_chain_head(db: Session) -> Optional[str]:
    """Return the record_hash of the most recently published QCO (chain head)."""
    latest = (
        db.query(QCORegistry)
        .filter(QCORegistry.published.is_(True))
        .order_by(QCORegistry.published_at.asc())
        .with_for_update(skip_locked=False)
        .all()
    )
    if not latest:
        return None
    return latest[-1].record_hash


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_qco_draft(
    db: Session,
    *,
    engagement_id: uuid.UUID,
    framework_covered: str,
    saro_version_assessed: str,
    sme_firm: str,
    sme_credential: Optional[str],
    scope_boundary_summary: Optional[str],
    document_url: Optional[str],
    document_sha256: Optional[str],
    created_by_user_id: uuid.UUID,
) -> QCORegistry:
    """Create a draft QCO. Requires the engagement gate to be locked (FR-EVF-08)."""
    if not gate_is_locked(db, engagement_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Cannot create a QCO: the Validation Gate for this engagement is not locked. "
                "All 7 gate items must be completed and the gate locked before a QCO can be created."
            ),
        )

    ref = generate_reference_number(db, framework_covered)
    qco = QCORegistry(
        qco_reference_number=ref,
        framework_covered=framework_covered,
        saro_version_assessed=saro_version_assessed,
        sme_firm=sme_firm,
        sme_credential=sme_credential,
        scope_boundary_summary=scope_boundary_summary,
        document_url=document_url,
        document_sha256=document_sha256,
        engagement_id=engagement_id,
        published=False,
        created_by_user_id=created_by_user_id,
    )
    db.add(qco)
    db.commit()
    db.refresh(qco)
    return qco


def get_qco(db: Session, qco_id: uuid.UUID) -> QCORegistry:
    qco = db.get(QCORegistry, qco_id)
    if qco is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QCO not found")
    return qco


def get_qco_by_ref(db: Session, ref: str) -> QCORegistry:
    qco = db.query(QCORegistry).filter(QCORegistry.qco_reference_number == ref).first()
    if qco is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"QCO '{ref}' not found")
    return qco


def list_qcos(
    db: Session,
    *,
    framework: Optional[str] = None,
    active_only: bool = False,
) -> list[QCORegistry]:
    q = db.query(QCORegistry)
    if framework:
        q = q.filter(QCORegistry.framework_covered == framework)
    if active_only:
        today = date.today()
        q = q.filter(
            QCORegistry.published.is_(True),
            QCORegistry.expiry_date >= today,
            QCORegistry.superseded_by_qco_id.is_(None),
        )
    return q.order_by(QCORegistry.created_at.desc()).all()


def update_qco_draft(
    db: Session,
    qco_id: uuid.UUID,
    *,
    updates: dict,
) -> QCORegistry:
    """Update a draft QCO. Raises QCOImmutableError if already published."""
    qco = get_qco(db, qco_id)
    if qco.published:
        raise QCOImmutableError(qco.qco_reference_number)

    allowed = {
        "saro_version_assessed", "sme_firm", "sme_credential",
        "scope_boundary_summary", "document_url", "document_sha256",
    }
    unknown = set(updates) - allowed
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown or immutable fields: {sorted(unknown)}. Editable: {sorted(allowed)}",
        )
    for field, value in updates.items():
        setattr(qco, field, value)
    qco.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(qco)
    return qco


def publish_qco(
    db: Session,
    qco_id: uuid.UUID,
    *,
    published_by_user_id: uuid.UUID,
    issue_date: Optional[date] = None,
    expiry_date: Optional[date] = None,
) -> QCORegistry:
    """
    Publish a QCO — sets published=True, stamps issue/expiry dates, computes
    record_hash, and emits a QCOPublicationEvent (FR-EVF-21).

    Immutable after this call — any subsequent edit raises QCOImmutableError.
    expiry_date must be <= issue_date + 365 days (FR-EVF-13).
    """
    qco = get_qco(db, qco_id)
    if qco.published:
        raise QCOImmutableError(qco.qco_reference_number)

    today = date.today()
    resolved_issue = issue_date or today
    resolved_expiry = expiry_date or (resolved_issue + timedelta(days=365))

    if resolved_expiry > resolved_issue + timedelta(days=MAX_VALIDITY_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"expiry_date {resolved_expiry} exceeds the maximum validity period of "
                f"{MAX_VALIDITY_DAYS} days from issue_date {resolved_issue} (FR-EVF-13)."
            ),
        )

    now = datetime.now(timezone.utc)

    # Capture chain head BEFORE marking published — prevents the current QCO
    # from appearing in its own chain-head query (flush would make it visible).
    prev_hash = _get_registry_chain_head(db)

    qco.issue_date = resolved_issue
    qco.expiry_date = resolved_expiry
    qco.published = True
    qco.published_at = now
    qco.published_by_user_id = published_by_user_id
    qco.updated_at = now
    qco.prev_hash = prev_hash

    # Hash chain — computed after all immutable fields are set
    qco.record_hash = _compute_record_hash(qco, prev_hash)

    db.flush()  # write updated state before publishing event

    # Emit publication event (FR-EVF-21) — written in the same transaction
    _write_publication_event(
        db,
        qco_reference_number=qco.qco_reference_number,
        artefact_identifier=f"qco:{qco.id}",
        publisher_user_id=published_by_user_id,
        distribution_channel="API",
    )

    db.commit()
    db.refresh(qco)
    return qco


def renew_qco(
    db: Session,
    qco_id: uuid.UUID,
    *,
    created_by_user_id: uuid.UUID,
    saro_version_assessed: Optional[str] = None,
    scope_boundary_summary: Optional[str] = None,
    document_url: Optional[str] = None,
    document_sha256: Optional[str] = None,
) -> QCORegistry:
    """
    Create a renewal draft from a published QCO.
    Marks the original as superseded once the renewal is published.
    The renewal starts as a draft; caller must separately call publish_qco().
    """
    original = get_qco(db, qco_id)
    if not original.published:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only published QCOs can be renewed. Publish the original first.",
        )

    renewal_ref = generate_reference_number(db, original.framework_covered)
    renewal = QCORegistry(
        qco_reference_number=renewal_ref,
        framework_covered=original.framework_covered,
        saro_version_assessed=saro_version_assessed or original.saro_version_assessed,
        sme_firm=original.sme_firm,
        sme_credential=original.sme_credential,
        scope_boundary_summary=scope_boundary_summary or original.scope_boundary_summary,
        document_url=document_url,
        document_sha256=document_sha256,
        engagement_id=original.engagement_id,
        published=False,
        renews_qco_id=original.id,
        created_by_user_id=created_by_user_id,
    )
    db.add(renewal)
    # Mark original as superseded
    original.superseded_by_qco_id = renewal.id  # will be set after flush
    db.flush()
    original.superseded_by_qco_id = renewal.id
    db.commit()
    db.refresh(renewal)
    return renewal


# ── Publication event writer (used by publish_qco + router) ──────────────────

def _write_publication_event(
    db: Session,
    *,
    qco_reference_number: str,
    artefact_identifier: str,
    publisher_user_id: uuid.UUID,
    distribution_channel: str,
) -> QCOPublicationEvent:
    """Write one append-only QCOPublicationEvent with hash-chain link."""
    from services.evf_publication_service import compute_publication_hash, get_publication_chain_head

    prev_hash = get_publication_chain_head(db)
    now = datetime.now(timezone.utc)
    event_id = uuid.uuid4()

    event_hash = compute_publication_hash(
        {
            "id": str(event_id),
            "qco_reference_number": qco_reference_number,
            "artefact_identifier": artefact_identifier,
            "publisher_user_id": str(publisher_user_id),
            "distribution_channel": distribution_channel,
            "timestamp": now.isoformat(),
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
    )
    db.add(event)
    return event
