"""
AI Insights routes.

GET  /api/v1/insights                — tenant-scoped insights derived read-only
                                       from Audit + ScanReport + AuditTrace
POST /api/v1/insights/{id}/action    — record accept / snooze / dismiss; appends
                                       an immutable AuditEvent row

Insights are evidence with remediation guidance — human validation required.
SARO never calls external AI models and never writes to client systems.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import (
    Audit,
    AuditEvent,
    AuditTrace,
    InsightAction,
    RiskMetadata,
    ScanReport,
    User,
)
from schemas import InsightActionIn
from services.insights_service import (
    build_insight,
    insight_id_for_audit,
    risk_id_for_audit,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

# Personas with read-only posture: may view insights, never act on them.
_READ_ONLY_PERSONAS = frozenset({"ai_auditor"})

_ACTION_EVENT_TYPES = {
    "accepted": "insight_suggestion_applied",
    "snoozed": "insight_snoozed",
    "dismissed": "insight_dismissed",
}
_ACTION_AUDIT_LABELS = {
    "accepted": "applied_suggestion",
    "snoozed": "snoozed",
    "dismissed": "dismissed",
}

# Audit UUID prefixes are hex only. Validating the stripped prefix prevents
# LIKE wildcard injection (%, _) and full-scan patterns (security audit F-1).
_HEX_PREFIX = re.compile(r"[0-9a-f]{1,32}")

# Upper bound on audit rows scanned per GET, independent of how many derive
# into insights — keeps DB work bounded on large tenants (security audit F-2).
_MAX_SCAN_WINDOW = 1000


def _safe_prefix(raw_id: str, *, strip: tuple[str, ...]) -> str | None:
    """Strip an id prefix and return the lowercase hex remainder, or None."""
    prefix = raw_id
    for p in strip:
        prefix = prefix.removeprefix(p)
    prefix = prefix.lower()
    if not _HEX_PREFIX.fullmatch(prefix):
        return None
    return prefix


def _audit_to_dict(audit: Audit) -> dict:
    return {"id": audit.id, "dataset_name": audit.dataset_name}


def _report_to_dict(report: ScanReport | None) -> dict | None:
    if report is None:
        return None
    return {
        "overall_risk_score": report.overall_risk_score,
        "confidence_score": report.confidence_score,
        "engine_version": report.engine_version,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def _trace_to_dict(trace: AuditTrace) -> dict:
    return {
        "gate_name": trace.gate_name,
        "check_type": trace.check_type,
        "check_name": trace.check_name,
        "result": trace.result,
        "reason": trace.reason,
        "remediation_hint": trace.remediation_hint,
    }


def _load_rows(db: Session, tenant_id, audit_prefix: str | None = None):
    q = (
        db.query(Audit, ScanReport, RiskMetadata, InsightAction)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .outerjoin(RiskMetadata, RiskMetadata.audit_id == Audit.id)
        .outerjoin(InsightAction, InsightAction.audit_id == Audit.id)
        .filter(Audit.tenant_id == tenant_id)
        .filter(Audit.status == "completed")
    )
    if audit_prefix:
        q = q.filter(cast(Audit.id, String).like(f"{audit_prefix}%"))
    return q.order_by(Audit.created_at.desc()).limit(_MAX_SCAN_WINDOW).all()


def _traces_by_audit(db: Session, audit_ids: list) -> dict:
    """One IN(...) query for all candidate audits — avoids per-audit N+1."""
    grouped: dict = {}
    if not audit_ids:
        return grouped
    for t in db.query(AuditTrace).filter(AuditTrace.audit_id.in_(audit_ids)).all():
        grouped.setdefault(t.audit_id, []).append(_trace_to_dict(t))
    return grouped


def _derive_from(audit, report, meta, action, traces: list[dict]) -> dict | None:
    if meta is not None and meta.dismissed:
        return None
    return build_insight(
        _audit_to_dict(audit),
        _report_to_dict(report),
        traces,
        action.status if action is not None else None,
    )


def _derive(db: Session, audit, report, meta, action) -> dict | None:
    traces = [
        _trace_to_dict(t)
        for t in db.query(AuditTrace).filter(AuditTrace.audit_id == audit.id).all()
    ]
    return _derive_from(audit, report, meta, action, traces)


@router.get("")
async def list_insights(
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    risk_id: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """
    Return AI insights for the caller's tenant, newest scan first.

    Optional risk_id (R-XXXXXX) narrows to one risk's insights. Insights are
    derived at read time; nothing is generated by an external model.
    """
    prefix = None
    if risk_id:
        prefix = _safe_prefix(risk_id, strip=("R-", "r-"))
        if prefix is None:
            # Malformed risk reference can never match an audit UUID prefix.
            return {"insights": [], "count": 0}
    logger.info("insights.fetch tenant=%s risk_id=%s", current.tenant_id, risk_id)

    rows = _load_rows(db, current.tenant_id, prefix)
    traces = _traces_by_audit(db, [audit.id for audit, _r, _m, _a in rows])

    insights: list[dict] = []
    for audit, report, meta, action in rows:
        insight = _derive_from(audit, report, meta, action, traces.get(audit.id, []))
        if insight is not None:
            insights.append(insight)
        if len(insights) >= limit:
            break

    logger.info(
        "insights.fetch.ok tenant=%s count=%d", current.tenant_id, len(insights)
    )
    return {"insights": insights, "count": len(insights)}


@router.post("/{insight_id}/action")
async def record_insight_action(
    insight_id: str,
    payload: InsightActionIn,
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Persist the reviewer's decision on an insight and append an immutable
    audit event. Repeated actions are last-write-wins.
    """
    if current.persona_role in _READ_ONLY_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only persona: auditors can view insights but cannot apply, snooze, or dismiss them.",
        )

    prefix = _safe_prefix(insight_id, strip=("INS-", "ins-"))
    if prefix is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found"
        )

    matches = (
        db.query(Audit, ScanReport, RiskMetadata, InsightAction)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .outerjoin(RiskMetadata, RiskMetadata.audit_id == Audit.id)
        .outerjoin(InsightAction, InsightAction.audit_id == Audit.id)
        .filter(Audit.tenant_id == current.tenant_id)
        .filter(cast(Audit.id, String).like(f"{prefix}%"))
        .limit(2)
        .all()
    )
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found"
        )
    if len(matches) > 1:
        # Two audits share this id prefix — refuse rather than act on the
        # wrong scan and pollute the audit trail (security audit F-3).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insight reference is ambiguous — refresh and retry.",
        )
    audit, report, meta, action = matches[0]

    # The insight must still be derivable — e.g. its risk may have been
    # dismissed since the card was rendered (STORY-002 edge: no orphan actions).
    if _derive(db, audit, report, meta, action) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found"
        )

    previous_status = action.status if action is not None else "active"
    resolved_id = insight_id_for_audit(audit.id)
    resolved_risk = risk_id_for_audit(audit.id)
    event_kwargs = {
        "tenant_id": current.tenant_id,
        "user_id": current.id,
        "event_type": _ACTION_EVENT_TYPES[payload.action],
        "event_data": {
            "action": _ACTION_AUDIT_LABELS[payload.action],
            "insight_id": resolved_id,
            "risk_id": resolved_risk,
            "audit_id": str(audit.id),
            "engine_version": report.engine_version if report else None,
            "human_review_acknowledged": payload.confirm_human_review,
            "previous_status": previous_status,
            "new_status": payload.action,
        },
    }

    if action is None:
        action = InsightAction(
            tenant_id=current.tenant_id,
            audit_id=audit.id,
            status=payload.action,
            acted_by_id=current.id,
        )
        db.add(action)
    else:
        action.status = payload.action
        action.acted_by_id = current.id

    db.add(AuditEvent(**event_kwargs))
    try:
        db.commit()
    except IntegrityError:
        # Two users applied the same fresh insight concurrently — the unique
        # audit_id constraint fired. Last write wins (STORY-002 edge).
        db.rollback()
        existing = (
            db.query(InsightAction).filter(InsightAction.audit_id == audit.id).first()
        )
        if existing is None:
            raise
        # The concurrent writer's status is the true prior state for the trail.
        event_kwargs["event_data"] = {
            **event_kwargs["event_data"],
            "previous_status": existing.status,
        }
        existing.status = payload.action
        existing.acted_by_id = current.id
        db.add(AuditEvent(**event_kwargs))
        db.commit()

    logger.info(
        "insights.action tenant=%s user=%s insight=%s action=%s",
        current.tenant_id,
        current.id,
        resolved_id,
        payload.action,
    )
    return {"id": resolved_id, "risk_id": resolved_risk, "status": payload.action}
