"""Observation-coverage / gap-attestation API (STORY-COV-001).

The CISO-facing continuity artifact: coverage %, gap list with causes, and max
observation lag. Plus the checkpoint interface a future adapter (STORY-406) calls.
Tenant-scoped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user, require_role, require_role_or_persona
from database import get_db
from models import ObservationGap
import services.observation_coverage_service as coverage

router = APIRouter(prefix="/api/v1/observation-coverage", tags=["observation-coverage"])

_require_read = require_role_or_persona(
    ("super_admin", "operator"), ("ai_auditor", "compliance_lead")
)


class CheckpointIn(BaseModel):
    # Bounded to the column width; watermark_position is constrained to an opaque-token
    # charset so free-text/PII cannot be smuggled into the evidence store (INV-2, security
    # review): identifiers/positions only, never observed content.
    system_id: str = Field(min_length=1, max_length=255)
    adapter_id: str = Field(min_length=1, max_length=255)
    watermark_position: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9:._\-+/=]+$")
    watermark_timestamp: datetime


@router.post(
    "/checkpoint",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    status_code=status.HTTP_201_CREATED,
    summary="Record an observation checkpoint (adapter interface)",
)
def record_checkpoint(
    payload: CheckpointIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cp = coverage.record_checkpoint(
        db,
        tenant_id=current_user.tenant_id,
        system_id=payload.system_id,
        adapter_id=payload.adapter_id,
        watermark_position=payload.watermark_position,
        watermark_timestamp=payload.watermark_timestamp,
    )
    return {"recorded": cp is not None, "deduped": cp is None}


@router.post(
    "/detect-gaps",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Sweep for observation gaps (internal cadence monitor)",
)
def detect_gaps(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    opened = coverage.detect_gaps(db, tenant_id=current_user.tenant_id)
    return {"opened": [str(g.id) for g in opened], "count": len(opened)}


@router.get(
    "/gaps", dependencies=[Depends(_require_read)], summary="List observation gaps"
)
def list_gaps(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    system_id: Optional[str] = None,
):
    q = db.query(ObservationGap).filter(
        ObservationGap.tenant_id == current_user.tenant_id
    )
    if system_id:
        q = q.filter(ObservationGap.system_id == system_id)
    rows = q.order_by(ObservationGap.gap_start.desc()).limit(500).all()
    return {
        "gaps": [
            {
                "id": str(g.id),
                "system_id": g.system_id,
                "adapter_id": g.adapter_id,
                "cause_class": g.cause_class,
                "gap_start": g.gap_start.isoformat(),
                "gap_end": g.gap_end.isoformat() if g.gap_end else None,
                "ongoing": g.gap_end is None,
                "retroactive": g.retroactive,
            }
            for g in rows
        ],
        "total": len(rows),
    }


@router.get(
    "/report",
    dependencies=[Depends(_require_read)],
    summary="Coverage report (diligence artifact)",
)
def report(
    system_id: str,
    start: datetime,
    end: datetime,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")
    return coverage.coverage_report(db, current_user.tenant_id, system_id, start, end)
