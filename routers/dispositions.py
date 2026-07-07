"""Finding disposition lifecycle API (STORY-DISP-001).

Persona-gated actions on failing-finding dispositions + the examiner report. Tenant-
scoped: a caller only ever reaches its own tenant's dispositions. Bulk-acknowledge is
permitted; bulk-waive is deliberately NOT offered (each waiver needs its own justification).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user, require_role_or_persona
from database import get_db
from models import Disposition
import services.disposition_service as disp_svc

router = APIRouter(prefix="/api/v1/dispositions", tags=["dispositions"])

_ACT_PERSONAS = ("risk_officer", "ai_auditor", "admin")
_require_act = require_role_or_persona(("super_admin", "operator"), _ACT_PERSONAS)
_require_read = require_role_or_persona(
    ("super_admin", "operator"), (*_ACT_PERSONAS, "compliance_lead")
)


class WaiveRequest(BaseModel):
    justification: str = Field(min_length=1)
    approver: str = Field(min_length=1)
    expiry: date
    reason: Optional[str] = None


class ReasonRequest(BaseModel):
    reason: Optional[str] = None


class BulkAckRequest(BaseModel):
    disposition_ids: list[uuid.UUID]


def _get_or_404(db: Session, disp_id: uuid.UUID, tenant_id: uuid.UUID) -> Disposition:
    disp = db.get(Disposition, disp_id)
    if disp is None or disp.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="disposition not found")
    return disp


def _serialize(d: Disposition) -> dict:
    return {
        "id": str(d.id),
        "state": d.state,
        "rule_id": d.rule_id,
        "gate_id": d.gate_id,
        "system_id": d.system_id,
        "severity": d.severity,
        "recurrence_count": d.recurrence_count,
        "waiver_expiry": d.waiver_expiry.isoformat() if d.waiver_expiry else None,
        "acknowledged_at": d.acknowledged_at.isoformat() if d.acknowledged_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("", dependencies=[Depends(_require_read)], summary="List dispositions")
def list_dispositions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    state: Optional[str] = None,
):
    q = db.query(Disposition).filter(Disposition.tenant_id == current_user.tenant_id)
    if state:
        q = q.filter(Disposition.state == state)
    rows = q.order_by(Disposition.created_at.desc()).limit(500).all()
    return {"dispositions": [_serialize(d) for d in rows], "total": len(rows)}


@router.get(
    "/report",
    dependencies=[Depends(_require_read)],
    summary="Disposition evidence report",
)
def get_report(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return disp_svc.disposition_report(db, current_user.tenant_id)


def _act(db, disp, fn, actor, reason):
    try:
        return fn(db, disp, actor=actor, reason=reason)
    except disp_svc.IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/{disp_id}/acknowledge",
    dependencies=[Depends(_require_act)],
    summary="Acknowledge",
)
def acknowledge(
    disp_id: uuid.UUID,
    payload: ReasonRequest = ReasonRequest(),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    disp = _get_or_404(db, disp_id, current_user.tenant_id)
    return _serialize(
        _act(db, disp, disp_svc.acknowledge, current_user.email, payload.reason)
    )


@router.post(
    "/{disp_id}/remediate", dependencies=[Depends(_require_act)], summary="Remediate"
)
def remediate(
    disp_id: uuid.UUID,
    payload: ReasonRequest = ReasonRequest(),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    disp = _get_or_404(db, disp_id, current_user.tenant_id)
    return _serialize(
        _act(db, disp, disp_svc.remediate, current_user.email, payload.reason)
    )


@router.post(
    "/{disp_id}/escalate", dependencies=[Depends(_require_act)], summary="Escalate"
)
def escalate(
    disp_id: uuid.UUID,
    payload: ReasonRequest = ReasonRequest(),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    disp = _get_or_404(db, disp_id, current_user.tenant_id)
    return _serialize(
        _act(db, disp, disp_svc.escalate, current_user.email, payload.reason)
    )


@router.post(
    "/{disp_id}/waive",
    dependencies=[Depends(_require_act)],
    summary="Waive (with justification)",
)
def waive(
    disp_id: uuid.UUID,
    payload: WaiveRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    disp = _get_or_404(db, disp_id, current_user.tenant_id)
    try:
        d = disp_svc.waive(
            db,
            disp,
            actor=current_user.email,
            justification=payload.justification,
            approver=payload.approver,
            expiry=payload.expiry,
            reason=payload.reason,
        )
    except disp_svc.IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except disp_svc.WaiverRequirementError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _serialize(d)


@router.post(
    "/bulk-acknowledge",
    dependencies=[Depends(_require_act)],
    summary="Bulk acknowledge",
)
def bulk_acknowledge(
    payload: BulkAckRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-acknowledge is permitted; bulk-waive is intentionally NOT offered (AC edge)."""
    acked = 0
    for did in payload.disposition_ids:
        disp = db.get(Disposition, did)
        if disp is None or disp.tenant_id != current_user.tenant_id:
            continue
        if disp.state == disp_svc.OPEN:
            disp_svc.acknowledge(
                db, disp, actor=current_user.email, reason="bulk-acknowledge"
            )
            acked += 1
    return {"acknowledged": acked}


@router.post(
    "/expire-waivers",
    dependencies=[Depends(require_role_or_persona(("super_admin", "operator"), ()))],
    summary="Sweep expired waivers -> auto-reopen (internal)",
)
def expire_waivers(
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    reopened = disp_svc.expire_waivers(db, tenant_id=current_user.tenant_id)
    return {"reopened": [str(d.id) for d in reopened], "count": len(reopened)}
