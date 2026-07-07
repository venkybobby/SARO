"""SARO self-audit spine (STORY-META-001).

An immutable, per-tenant hash-chained trail of privileged/sensitive actions WITHIN
SARO — so the platform survives the same scrutiny it applies to customers. Reuses
the grc/evidence.py DB chain discipline (per-tenant seq + content_hash + chain_hash);
we do not reinvent the crypto.

Content-free by construction: only metadata is hashed and stored — actor, action
class, target identifier, outcome, timestamp — never payload/evidence content
(INV-2/INV-3 apply to the audit trail itself; a log that copies evidence content
becomes a retention violation).

Fail modes (AC edge):
  * record_privileged() FAILS CLOSED — raises if the event cannot be persisted, so
    an unauditable privileged action aborts.
  * record_access() FAILS OPEN — logs a data-quality warning and continues, because
    the customer's compliance-function availability beats SARO's self-audit
    completeness (documented tradeoff).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from config import settings
from models import AuditEvent

logger = logging.getLogger(__name__)

GENESIS = "GENESIS"

# Closed action-class vocabulary (AC — v1 closed set).
RULE_PACK_CHANGE = "RULE_PACK_CHANGE"
EVIDENCE_ACCESS = "EVIDENCE_ACCESS"
DISPOSITION_ACTION = "DISPOSITION_ACTION"
ADMIN_ACTION = "ADMIN_ACTION"
AUTH_EVENT = "AUTH_EVENT"
EXPORT = "EXPORT"
ACTION_CLASSES = frozenset(
    {
        RULE_PACK_CHANGE,
        EVIDENCE_ACCESS,
        DISPOSITION_ACTION,
        ADMIN_ACTION,
        AUTH_EVENT,
        EXPORT,
    }
)

OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_FAILURE = "FAILURE"
OUTCOME_DENIED = "DENIED"

# Well-known SYSTEM tenant for global / out-of-band actions (rule-pack changes are
# global, not tenant-specific). Seeded by migration 033. The leading 'a' is deliberate:
# an all-numeric UUID would be coerced to an integer by SQLite's NUMERIC type affinity
# in the test harness (real Postgres UUID columns are unaffected).
SYSTEM_TENANT_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")

# Fields sealed into the per-event content hash (metadata only).
_HASHED_FIELDS = (
    "action_class",
    "actor",
    "target_type",
    "target_id",
    "outcome",
    "timestamp",
)


class UnauditableActionError(Exception):
    """A privileged action could not be recorded — fail closed, abort the action."""


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _content_hash(
    *,
    action_class: str,
    actor: str,
    target_type: Optional[str],
    target_id: Optional[str],
    outcome: str,
    timestamp: str,
) -> str:
    payload = {
        "action_class": action_class,
        "actor": actor,
        "target_type": target_type or "",
        "target_id": target_id or "",
        "outcome": outcome,
        "timestamp": timestamp,
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _chain_hash(content_hash: str, prev_hash: Optional[str]) -> str:
    return hashlib.sha256(
        (content_hash + (prev_hash or GENESIS)).encode("utf-8")
    ).hexdigest()


def _chain_tail(db: Session, tenant_id: uuid.UUID) -> tuple[Optional[str], int]:
    """Return (last event_hash, last seq) for a tenant's chained events, or (None, 0).

    with_for_update() locks the tail row so same-tenant appends serialize. On an EMPTY
    chain there is no tail row to lock, so two concurrent genesis inserts can both
    compute seq=1 — the ux_audit_events_tenant_seq partial unique index is the backstop
    (one insert fails; record_privileged then raises, record_access logs and drops).
    """
    row = (
        db.query(AuditEvent.event_hash, AuditEvent.seq)
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.seq.isnot(None))
        .order_by(AuditEvent.seq.desc())
        .with_for_update()
        .first()
    )
    return (row[0], row[1]) if row else (None, 0)


def record_event(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor: str,
    action_class: str,
    outcome: str = OUTCOME_SUCCESS,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    """Append one chained, content-free self-audit event to a tenant's chain.

    Raises ValueError for an unknown action_class. Commits the row.
    """
    if action_class not in ACTION_CLASSES:
        raise ValueError(f"unknown action_class: {action_class}")

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    content_hash = _content_hash(
        action_class=action_class,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        timestamp=timestamp,
    )
    prev_hash, last_seq = _chain_tail(db, tenant_id)
    event_hash = _chain_hash(content_hash, prev_hash)

    event_data = dict(metadata or {})
    event_data["timestamp"] = timestamp
    event_data["content_hash"] = content_hash

    evt = AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=action_class.lower(),
        event_data=event_data,
        action_class=action_class,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        retroactive=False,
        seq=last_seq + 1,
        prev_hash=prev_hash,
        event_hash=event_hash,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


def record_privileged(db: Session, **kwargs) -> AuditEvent:
    """Fail-closed recording for privileged/admin actions (raises if unauditable)."""
    try:
        return record_event(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 — fail closed: the action must abort
        db.rollback()
        raise UnauditableActionError(
            f"privileged action could not be audited ({kwargs.get('action_class')}) — aborted"
        ) from exc


def record_access(db: Session, **kwargs) -> Optional[AuditEvent]:
    """Fail-open recording for evidence reads (logs a data-quality alarm, continues)."""
    try:
        return record_event(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 — fail open: availability beats self-audit completeness
        db.rollback()
        logger.warning(
            "DATA-QUALITY: self-audit record_access failed for %s (continuing): %s",
            kwargs.get("action_class"),
            exc,
        )
        return None


def verify_audit_chain(db: Session, tenant_id: uuid.UUID) -> dict:
    """Replay a tenant's chained events (seq NOT NULL) and flag the first tampered one.

    Retroactive / out-of-band (unchained) events are excluded — they are captured and
    queryable but honestly outside the app-layer chain.
    """
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.seq.isnot(None))
        .order_by(AuditEvent.seq.asc())
        .all()
    )
    prev_hash: Optional[str] = None
    for index, e in enumerate(events):
        if e.seq != index + 1:
            return {
                "valid": False,
                "break_at_seq": e.seq,
                "reason": "seq not contiguous",
            }
        content = _content_hash(
            action_class=e.action_class or "",
            actor=e.actor or "",
            target_type=e.target_type,
            target_id=e.target_id,
            outcome=e.outcome or "",
            timestamp=(e.event_data or {}).get("timestamp", ""),
        )
        expected = _chain_hash(content, prev_hash)
        if e.prev_hash != prev_hash or e.event_hash != expected:
            return {"valid": False, "break_at_seq": e.seq, "reason": "hash mismatch"}
        prev_hash = e.event_hash
    return {"valid": True, "events_checked": len(events), "break_at_seq": None}


def query_events(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    actor: Optional[str] = None,
    action_class: Optional[str] = None,
    target_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 200,
) -> list[AuditEvent]:
    """Filtered audit query (AC-4). Tenant-scoped; newest first."""
    q = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id)
    if actor:
        q = q.filter(AuditEvent.actor == actor)
    if action_class:
        q = q.filter(AuditEvent.action_class == action_class)
    if target_id:
        q = q.filter(AuditEvent.target_id == target_id)
    if since:
        q = q.filter(AuditEvent.created_at >= since)
    if until:
        q = q.filter(AuditEvent.created_at <= until)
    return q.order_by(AuditEvent.created_at.desc()).limit(limit).all()


# ── retention (AC-5): archival, never silent deletion ───────────────────────────
def find_archival_candidates(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    now: Optional[datetime] = None,
    retention_days: Optional[int] = None,
) -> list[AuditEvent]:
    """Events older than the hot-retention floor — candidates for ARCHIVAL, not deletion."""
    now = now or datetime.now(tz=timezone.utc)
    days = (
        retention_days
        if retention_days is not None
        else settings.saro_audit_retention_days
    )
    cutoff = now - timedelta(days=days)
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.created_at < cutoff)
        .all()
    )


def record_retention_sweep(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    now: Optional[datetime] = None,
    actor: str = "system:retention",
) -> int:
    """AC-5: identify past-retention events and record an archival ADMIN_ACTION event.

    Archival-not-deletion: this NEVER deletes rows — it records the intent and count so
    the trail shows retention was applied. The physical archival mover (to cold storage)
    is a documented follow-on ("evidence spine, not the program"). Returns the candidate count.
    """
    candidates = find_archival_candidates(db, tenant_id, now=now)
    record_event(
        db,
        tenant_id=tenant_id,
        actor=actor,
        action_class=ADMIN_ACTION,
        target_type="audit_retention",
        target_id=f"retention_{settings.saro_audit_retention_days}d",
        metadata={
            "archival_candidates": len(candidates),
            "policy": "archive-not-delete",
        },
    )
    return len(candidates)
