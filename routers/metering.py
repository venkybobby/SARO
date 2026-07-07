"""Usage metering API (STORY-MTR-001).

Founder/operator-facing: per-tenant usage totals, the immutable usage statement
artifact, and on-demand reconciliation. Tenant-scoped.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user, require_role_or_persona
from database import get_db
import services.metering_service as metering

router = APIRouter(prefix="/api/v1/metering", tags=["metering"])

_require = require_role_or_persona(("super_admin", "operator"), ("admin",))
_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _resolve_period(period: Optional[str]) -> str:
    """Validate a 'YYYY-MM' period (422 on bad format) or default to the current one."""
    if period is None:
        return metering.current_period()
    if not _PERIOD_RE.match(period):
        raise HTTPException(status_code=422, detail="period must be 'YYYY-MM'")
    return period


@router.get(
    "/usage", dependencies=[Depends(_require)], summary="Current-period usage totals"
)
def usage(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    period: Optional[str] = None,
):
    period = _resolve_period(period)
    return {
        "period": period,
        "totals": metering.meter_totals(db, current_user.tenant_id, period),
    }


@router.post(
    "/statement",
    dependencies=[Depends(_require)],
    summary="Issue the immutable usage statement",
)
def statement(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    period: Optional[str] = None,
):
    period = _resolve_period(period)
    stmt = metering.generate_statement(db, current_user.tenant_id, period)
    return {
        "id": str(stmt.id),
        "period": stmt.period_bucket,
        "totals": stmt.totals,
        "content_hash": stmt.content_hash,
        "issued_at": stmt.issued_at.isoformat() if stmt.issued_at else None,
    }


@router.get(
    "/reconcile",
    dependencies=[Depends(_require)],
    summary="Reconcile meters vs authoritative counts",
)
def reconcile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    period: Optional[str] = None,
):
    return metering.reconcile(db, current_user.tenant_id, _resolve_period(period))
