"""Audit chain verification endpoint (AUD-001 / AUD-002).

Verifies the SHA-256 integrity of an audit's hash chain.  Each AuditTrace
row's event_hash must recompute from the same canonical payload used at
write time (see hash_chain_service.build_event_payload).

Security properties enforced here:
  - audit_id is REQUIRED — no full-table cross-tenant scan path.
  - Tenant ownership is verified before chain traversal (prevents IDOR).
  - Rate limiting is enforced per user (in-memory LRU; Redis upgrade tracked
    as AUD-RATE-001 for multi-worker deployments).
  - Verification is strictly read-only — no write side effects.
"""
import time
import uuid
from collections import OrderedDict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from services.hash_chain_service import (
    LEGACY_SENTINEL,
    compute_event_hash,
)
from models import Audit, AuditTrace

router = APIRouter(prefix="/api/v1/audit", tags=["audit-chain"])

# In-memory rate limiter (LRU-capped to bound memory growth).
# NOTE: ineffective across multiple uvicorn workers — replace with Redis
# SETEX/EXISTS before scaling to multi-worker. Tracked: AUD-RATE-001.
_verify_last_called: OrderedDict[str, float] = OrderedDict()
_RATE_LIMIT_SECONDS = 60
_RATE_LIMIT_MAX_ENTRIES = 10_000


def _check_rate_limit(user_id: str) -> None:
    now = time.time()
    last = _verify_last_called.get(user_id, 0)
    remaining = int(_RATE_LIMIT_SECONDS - (now - last))
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail="Rate limit: 1 call per minute",
            headers={"Retry-After": str(remaining)},
        )
    _verify_last_called[user_id] = now
    _verify_last_called.move_to_end(user_id)
    while len(_verify_last_called) > _RATE_LIMIT_MAX_ENTRIES:
        _verify_last_called.popitem(last=False)


def _event_dict(t: AuditTrace) -> dict:
    """Reconstruct the raw event data dict from a persisted AuditTrace.

    Returns the same shape dict that _persist_traces() passes to
    compute_event_hash() — do NOT pre-process through build_event_payload()
    here, because compute_event_hash() calls build_event_payload() internally.
    Double-wrapping would cause the "id" → "event_id" mapping to be applied
    twice, producing the wrong canonical payload and false chain failures.
    """
    return {
        "id": str(t.id),
        "audit_id": str(t.audit_id),
        "gate_id": str(t.gate_id),
        "gate_name": str(t.gate_name or ""),
        "check_type": str(t.check_type or ""),
        "check_name": str(t.check_name or ""),
        "result": str(t.result),
        "reason": str(t.reason or ""),
        "signal_text": str(t.signal_text or "") if hasattr(t, "signal_text") else "",
        "remediation_hint": str(t.remediation_hint or "") if hasattr(t, "remediation_hint") else "",
        "created_at": t.created_at.isoformat(),
    }


@router.get("/verify-chain")
def verify_audit_chain(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Verify the SHA-256 integrity of a single audit's hash chain.

    Requires audit_id — omitting it is rejected (no full-table scan path).
    Tenancy is enforced: only the owning tenant may verify their audit.

    Returns a structured result distinguishing:
      - "verified": all hashes match, chain is intact
      - "chain_integrity_failed": one or more hashes do not match
      - "legacy_unverifiable": all records predate AUD-001 migration
      - "partial_legacy": mixed pre- and post-migration records
      - "no_events": audit exists but has no trace records
    """
    _check_rate_limit(str(current_user.id))

    # Verify the audit exists and belongs to the caller's tenant.
    audit = (
        db.query(Audit)
        .filter(Audit.id == audit_id, Audit.tenant_id == current_user.tenant_id)
        .first()
    )
    if audit is None:
        raise HTTPException(status_code=404, detail="audit_not_found")

    traces = (
        db.query(AuditTrace)
        .filter(AuditTrace.audit_id == audit_id)
        .order_by(AuditTrace.created_at.asc(), AuditTrace.id.asc())
        .all()
    )

    if not traces:
        return {
            "valid": None,
            "status": "no_events",
            "events_checked": 0,
            "broken_at": None,
        }

    legacy_count = sum(
        1 for t in traces if t.event_hash == LEGACY_SENTINEL or t.event_hash is None
    )
    chain_count = len(traces) - legacy_count

    if legacy_count == len(traces):
        return {
            "valid": None,
            "status": "legacy_unverifiable",
            "events_checked": len(traces),
            "message": (
                "All records predate hash chain migration (AUD-001). "
                "Integrity cannot be verified for this audit."
            ),
            "broken_at": None,
        }

    if legacy_count > 0 and chain_count > 0:
        chain_traces = [
            t for t in traces
            if t.event_hash != LEGACY_SENTINEL and t.event_hash is not None
        ]
        # Seed prev_hash from the first chain-enabled event's stored prev_hash
        # so we verify from the correct chain anchor, not from GENESIS.
        result = _verify_chain_segment(
            chain_traces, seed_prev=chain_traces[0].prev_hash
        )
        result["status"] = "partial_legacy"
        result["legacy_events_skipped"] = legacy_count
        return result

    result = _verify_chain_segment(traces)
    result["status"] = "verified" if result["valid"] else "chain_integrity_failed"
    return result


def _verify_chain_segment(
    traces: list[AuditTrace],
    *,
    seed_prev: Optional[str] = None,
) -> dict:
    """Recompute and verify hashes for a list of chain-enabled AuditTrace records.

    Args:
        traces:    Ordered list of AuditTrace ORM objects (ascending created_at).
        seed_prev: Initial prev_hash anchor.  None = start from GENESIS.
                   Pass chain_traces[0].prev_hash for partial-legacy segments.
    """
    if not traces:
        return {"valid": True, "events_checked": 0, "broken_at": None}

    prev_hash: Optional[str] = seed_prev

    for i, t in enumerate(traces):
        expected = compute_event_hash(_event_dict(t), prev_hash)
        actual = t.event_hash

        if expected != actual:
            return {
                "valid": False,
                "events_checked": i + 1,
                "broken_at": {
                    "sequence_position": i,
                    "record_id": str(t.id),
                    "expected_hash": expected,
                    "actual_hash": actual,
                    "reason": "hash_mismatch",
                },
            }

        # Verify that this event's prev_hash pointer matches its predecessor.
        if i > 0 and t.prev_hash != traces[i - 1].event_hash:
            return {
                "valid": False,
                "events_checked": i + 1,
                "broken_at": {
                    "sequence_position": i,
                    "record_id": str(t.id),
                    "expected_prev_hash": traces[i - 1].event_hash,
                    "actual_prev_hash": t.prev_hash,
                    "reason": "prev_hash_mismatch",
                },
            }

        prev_hash = actual

    return {
        "valid": True,
        "events_checked": len(traces),
        "broken_at": None,
    }
