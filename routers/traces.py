"""
Audit Trace & Remedy routes.

GET  /api/v1/traces/{audit_id}                      — all traces for an audit
GET  /api/v1/traces/{audit_id}/failed               — fail/warn/flagged traces only
GET  /api/v1/traces/{audit_id}/summary              — aggregated trace statistics
POST /api/v1/traces/{audit_id}/{trace_id}/remediate — mark a trace as remediated
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import Audit, AuditTrace, SampleFinding, User
from schemas import AuditTraceOut, RemediateTraceIn, SampleFindingOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/traces", tags=["traces"])

_FAILED_RESULTS = {"fail", "warn", "flagged", "triggered"}


def _get_audit_or_404(
    audit_id: uuid.UUID, tenant_id: uuid.UUID, db: Session
) -> Audit:
    """Return the audit or raise 404 if not found / wrong tenant."""
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    return audit


@router.get(
    "/{audit_id}",
    response_model=list[AuditTraceOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="All trace records for an audit (full pipeline log)",
)
def get_traces(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    gate_id: int | None = Query(default=None, description="Filter by gate (1–4)"),
    result: str | None = Query(
        default=None, description="Filter by result: pass|fail|warn|flagged|triggered"
    ),
) -> list[AuditTraceOut]:
    """Return all traces for the given audit, ordered by gate then creation time."""
    _get_audit_or_404(audit_id, current_user.tenant_id, db)

    q = (
        db.query(AuditTrace)
        .filter(AuditTrace.audit_id == audit_id)
        .order_by(AuditTrace.gate_id, AuditTrace.created_at)
    )
    if gate_id is not None:
        q = q.filter(AuditTrace.gate_id == gate_id)
    if result:
        q = q.filter(AuditTrace.result == result)

    return [AuditTraceOut.model_validate(t) for t in q.all()]


@router.get(
    "/{audit_id}/failed",
    response_model=list[AuditTraceOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Failed/warn traces only — drives the Remedy screen",
)
def get_failed_traces(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_remediated: bool = Query(
        default=False,
        description="Include traces already marked as remediated",
    ),
) -> list[AuditTraceOut]:
    """
    Return only the traces that need attention (fail / warn / flagged / triggered).
    By default, already-remediated items are excluded.
    """
    _get_audit_or_404(audit_id, current_user.tenant_id, db)

    q = (
        db.query(AuditTrace)
        .filter(
            AuditTrace.audit_id == audit_id,
            AuditTrace.result.in_(list(_FAILED_RESULTS)),
        )
        .order_by(AuditTrace.gate_id, AuditTrace.created_at)
    )
    if not include_remediated:
        q = q.filter(AuditTrace.is_remediated == False)  # noqa: E712

    return [AuditTraceOut.model_validate(t) for t in q.all()]


@router.get(
    "/{audit_id}/summary",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Aggregated trace statistics for an audit",
)
def get_trace_summary(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Return counts and breakdown across all trace records for the audit."""
    _get_audit_or_404(audit_id, current_user.tenant_id, db)

    traces = (
        db.query(AuditTrace)
        .filter(AuditTrace.audit_id == audit_id)
        .all()
    )

    by_gate: dict[str, dict] = {}
    total_failed = 0
    total_remediated = 0

    for t in traces:
        gate_key = f"Gate {t.gate_id}: {t.gate_name}"
        if gate_key not in by_gate:
            by_gate[gate_key] = {
                "pass": 0, "fail": 0, "warn": 0,
                "flagged": 0, "triggered": 0, "other": 0,
            }
        bucket = t.result if t.result in by_gate[gate_key] else "other"
        by_gate[gate_key][bucket] += 1
        if t.result in _FAILED_RESULTS:
            total_failed += 1
        if t.is_remediated:
            total_remediated += 1

    return {
        "audit_id": str(audit_id),
        "total_traces": len(traces),
        "total_failed": total_failed,
        "total_remediated": total_remediated,
        "pending_remediation": total_failed - total_remediated,
        "by_gate": by_gate,
    }


@router.get(
    "/{audit_id}/samples",
    response_model=list[SampleFindingOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Per-sample Gate 3 findings for an audit (SARO-001)",
)
def get_sample_findings(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    domain: str | None = Query(default=None, description="Filter by MIT domain"),
) -> list[SampleFindingOut]:
    """
    Return the per-sample Gate 3 risk signal matches for the audit.

    Enables governance leads to drill from a domain-level AuditTrace flag down to
    the specific sample IDs and (redacted) text fragments that triggered it.
    Results are scoped to the caller's tenant.
    """
    _get_audit_or_404(audit_id, current_user.tenant_id, db)

    q = (
        db.query(SampleFinding)
        .filter(SampleFinding.audit_id == audit_id)
        .order_by(SampleFinding.domain, SampleFinding.created_at)
    )
    if domain:
        q = q.filter(SampleFinding.domain == domain)

    return [SampleFindingOut.model_validate(f) for f in q.all()]


@router.post(
    "/{audit_id}/{trace_id}/remediate",
    response_model=AuditTraceOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Mark a trace item as remediated",
)
def remediate_trace(
    audit_id: uuid.UUID,
    trace_id: uuid.UUID,
    payload: RemediateTraceIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditTraceOut:
    """
    Mark a specific trace item as reviewed and remediated by the current user.
    Appends optional operator notes to the reason field for audit trail.
    """
    _get_audit_or_404(audit_id, current_user.tenant_id, db)

    trace = db.get(AuditTrace, trace_id)
    if not trace or trace.audit_id != audit_id:
        raise HTTPException(status_code=404, detail="Trace record not found")

    trace.is_remediated = True
    trace.remediated_at = datetime.now(tz=timezone.utc)
    trace.remediated_by_id = current_user.id

    if payload.notes:
        prefix = trace.reason or ""
        trace.reason = (
            f"{prefix}\n\n[Remediation note by {current_user.email}]: {payload.notes}".strip()
        )

    db.commit()
    db.refresh(trace)
    logger.info(
        "Trace %s (audit=%s, gate=%d, check=%s) marked remediated by %s",
        trace_id, audit_id, trace.gate_id, trace.check_name, current_user.email,
    )
    return AuditTraceOut.model_validate(trace)
