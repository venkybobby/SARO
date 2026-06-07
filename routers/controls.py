"""
Unified Control Library API (SAR-010).

GET  /api/v1/controls                     — list controls, optionally filtered by framework(s)
GET  /api/v1/controls/{id}/evidence       — audit trace IDs serving as evidence for this control
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Audit, AuditTrace, Control, ControlFrameworkMapping, User

router = APIRouter(prefix="/api/v1/controls", tags=["controls"])


def _control_to_dict(ctrl: Control, mappings: list[ControlFrameworkMapping]) -> dict[str, Any]:
    return {
        "id": str(ctrl.id),
        "control_id": ctrl.control_id,
        "title": ctrl.title,
        "description": ctrl.description,
        "control_type": ctrl.control_type,
        "status": ctrl.status,
        "evidence_count": ctrl.evidence_count,
        "last_assessed_date": ctrl.last_assessed_date.isoformat() if ctrl.last_assessed_date else None,
        "frameworks": [
            {"framework": m.framework, "clause_reference": m.clause_reference}
            for m in mappings
        ],
    }


@router.get("", summary="List controls, optionally filtered by framework(s)")
def list_controls(
    frameworks: list[str] = Query(default=[], alias="frameworks"),
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[dict[str, Any]]:
    """
    Return all controls. Pass `?frameworks=ISO_42001&frameworks=EU_AI_ACT` to
    filter to controls tagged to any of the given frameworks.
    """
    if frameworks:
        # Controls that have at least one mapping to one of the requested frameworks
        matching_ids = (
            db.query(ControlFrameworkMapping.control_id)
            .filter(ControlFrameworkMapping.framework.in_(frameworks))
            .distinct()
            .subquery()
        )
        controls = (
            db.query(Control)
            .filter(Control.id.in_(matching_ids), Control.status != "deprecated")
            .order_by(Control.control_id)
            .all()
        )
    else:
        controls = (
            db.query(Control)
            .filter(Control.status != "deprecated")
            .order_by(Control.control_id)
            .all()
        )

    result = []
    for ctrl in controls:
        mappings = (
            db.query(ControlFrameworkMapping)
            .filter(ControlFrameworkMapping.control_id == ctrl.id)
            .all()
        )
        result.append(_control_to_dict(ctrl, mappings))
    return result


@router.get("/{control_id}/evidence", summary="Audit trace IDs serving as evidence for a control")
def control_evidence(
    control_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """
    Returns audit trace IDs that can be cited as evidence for the control.
    Traces are matched by domain name alignment — controls tagged to risk domains
    have evidence from AuditTrace rows where check_name contains relevant domains.
    """
    ctrl = db.query(Control).filter(Control.id == control_id).first()
    if not ctrl:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Control not found")

    # Match traces where check_name is relevant to the control title keywords
    title_keywords = [w.lower() for w in ctrl.title.split() if len(w) > 4]
    # Fetch recent completed audit traces for the tenant and filter by title overlap
    trace_ids: list[str] = []
    if title_keywords:
        traces = (
            db.query(AuditTrace)
            .join(Audit, AuditTrace.audit_id == Audit.id)
            .filter(
                Audit.tenant_id == current_user.tenant_id,
                Audit.status == "completed",
            )
            .limit(200)
            .all()
        )
        for tr in traces:
            cn_lower = tr.check_name.lower()
            if any(kw in cn_lower for kw in title_keywords):
                trace_ids.append(str(tr.id))
                if len(trace_ids) >= 50:
                    break

    return {
        "control_id": str(control_id),
        "control_title": ctrl.title,
        "evidence_trace_ids": trace_ids,
        "evidence_count": len(trace_ids),
    }
