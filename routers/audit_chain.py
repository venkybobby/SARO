"""Audit chain verification and RFC 3161 timestamping endpoints."""
import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from services.hash_chain_service import verify_chain, compute_event_hash
from models import AuditTrace

router = APIRouter(prefix="/api/v1/audit", tags=["audit-chain"])

# Simple in-memory rate limiter (1 req/min per user)
_verify_last_called: dict[str, float] = {}
RATE_LIMIT_SECONDS = 60


def _check_rate_limit(user_id: str):
    now = time.time()
    last = _verify_last_called.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        raise HTTPException(status_code=429, detail="Rate limit: 1 call per minute")
    _verify_last_called[user_id] = now


@router.get("/verify-chain")
def verify_audit_chain(
    audit_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Verify the integrity of the audit hash chain.

    Rate-limited to 1 call per minute (expensive query).
    """
    _check_rate_limit(str(current_user.id))

    query = db.query(AuditTrace).order_by(AuditTrace.created_at.asc())
    if audit_id:
        query = query.filter(AuditTrace.audit_id == audit_id)

    traces = query.all()
    events = [
        {
            "id": t.id,
            "audit_id": t.audit_id,
            "gate_id": t.gate_id,
            "result": t.result,
            "reason": t.reason,
            "created_at": str(t.created_at),
            "prev_hash": getattr(t, "prev_hash", None),
            "event_hash": getattr(t, "event_hash", None),
        }
        for t in traces
    ]
    return verify_chain(events)
