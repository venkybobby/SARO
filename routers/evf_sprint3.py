"""
EVF Sprint 3 router — Validation Status (FR-EVF-11) + Expiry Alerts (FR-EVF-13).

Prefix: /api/v1/evf

Endpoints added:
  GET /validation-status              — all 4 frameworks
  GET /validation-status/{framework}  — single framework
  GET /qco/expiry-alerts              — pending expiry notifications (Sales dashboard)
  POST /admin/expiry-scan             — manual trigger for testing / on-demand (super_admin)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from models import EVFFramework, QCOExpiryNotification
from services.evf_expiry_service import scan_qco_expiry
from services.evf_validation_status_service import (
    get_all_framework_statuses,
    get_validation_status,
)

router = APIRouter(prefix="/api/v1/evf", tags=["EVF"])

_VALID_FRAMEWORKS = {f.value for f in EVFFramework}


# ── Validation Status endpoints ───────────────────────────────────────────────


@router.get(
    "/validation-status",
    dependencies=[Depends(get_current_user)],
    summary="Get EVF validation status for all 4 frameworks (FR-EVF-11)",
    response_description=(
        "Returns current Tier 1/2/3 label for each framework. "
        "Tier 1 = QCO active. Tier 2 = under review. Tier 3 = not assessed."
    ),
)
async def get_all_validation_statuses(
    db: Session = Depends(get_db),
) -> list[dict]:
    # CHUB-010: intentionally NOT tenant-scoped. get_all_framework_statuses() reads
    # QCORegistry (models.py:894), SMEEngagement (models.py:793) and
    # QCOExpiryNotification (models.py:991) — none declare a tenant_id column. SARO's
    # external-validation (EVF) tier per framework is a single product-level fact
    # (docs/COMPLIANCE_CLAIMS_MATRIX.md, EVF section), identical for every tenant;
    # there is no per-tenant validation row to leak. Pinned by
    # tests/test_chub010_tenant_scoping.py.
    return get_all_framework_statuses(db)


@router.get(
    "/validation-status/{framework}",
    dependencies=[Depends(get_current_user)],
    summary="Get EVF validation status for a single framework (FR-EVF-11)",
)
async def get_single_validation_status(
    framework: str,
    db: Session = Depends(get_db),
) -> dict:
    if framework not in _VALID_FRAMEWORKS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"framework must be one of {sorted(_VALID_FRAMEWORKS)}",
        )
    return get_validation_status(db, framework)


# ── Expiry Alerts endpoint ────────────────────────────────────────────────────


@router.get(
    "/qco/expiry-alerts",
    dependencies=[Depends(get_current_user)],
    summary="List QCO expiry notifications — Sales dashboard polling endpoint (FR-EVF-13)",
)
async def list_expiry_alerts(
    framework: Optional[str] = Query(None),
    notification_type: Optional[str] = Query(
        None,
        description="Filter by type: T_MINUS_60 | T_MINUS_30 | T_MINUS_7 | EXPIRED | SALES_NOTIFY",
    ),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    if framework and framework not in _VALID_FRAMEWORKS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"framework must be one of {sorted(_VALID_FRAMEWORKS)}",
        )

    q = db.query(QCOExpiryNotification).order_by(QCOExpiryNotification.sent_at.desc())
    if framework:
        q = q.filter(QCOExpiryNotification.framework == framework)
    if notification_type:
        q = q.filter(QCOExpiryNotification.notification_type == notification_type)

    alerts = q.limit(limit).all()
    return [
        {
            "id":                  str(a.id),
            "qco_reference_number": a.qco_reference_number,
            "framework":           a.framework,
            "notification_type":   a.notification_type,
            "expires_in_days":     a.expires_in_days,
            "sent_at":             a.sent_at.isoformat() if a.sent_at else None,
        }
        for a in alerts
    ]


# ── Admin: manual expiry scan trigger ────────────────────────────────────────


@router.post(
    "/admin/expiry-scan",
    dependencies=[Depends(require_role("super_admin"))],
    status_code=status.HTTP_200_OK,
    summary="Manually trigger QCO expiry scan (super_admin — for testing / on-demand)",
)
async def trigger_expiry_scan(db: Session = Depends(get_db)) -> dict:
    result = scan_qco_expiry(db)
    return {"status": "ok", "result": result}
