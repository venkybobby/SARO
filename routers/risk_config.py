"""
Tenant Risk Configuration — SARO-003.

GET  /api/v1/risk-config          — fetch current tenant risk config
PUT  /api/v1/risk-config          — upsert tenant risk config (super_admin only)
DELETE /api/v1/risk-config        — reset to defaults (super_admin only)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from engine import MIT_DOMAINS
from models import TenantRiskConfig, User
from schemas import RiskConfigIn, TenantRiskConfigOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/risk-config", tags=["risk-config"])


async def _require_risk_config_writer(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """PT-010 (AC-2): risk-config writes require super_admin role OR the risk_officer persona."""
    if current_user.role == "super_admin" or getattr(current_user, "persona_role", None) == "risk_officer":
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Risk configuration may only be changed by a super_admin or the Risk Officer persona.",
    )


@router.get(
    "",
    response_model=TenantRiskConfigOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get current tenant risk configuration",
)
def get_risk_config(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantRiskConfigOut:
    """Return the tenant's current risk signal weight/suppression config, or defaults if not set."""
    cfg = db.query(TenantRiskConfig).filter(
        TenantRiskConfig.tenant_id == current_user.tenant_id
    ).first()
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No risk configuration set for this tenant — engine defaults are active.",
        )
    return TenantRiskConfigOut.model_validate(cfg)


@router.put(
    "",
    response_model=TenantRiskConfigOut,
    dependencies=[Depends(_require_risk_config_writer)],
    summary="Upsert tenant risk configuration (super_admin or Risk Officer)",
)
def upsert_risk_config(
    payload: RiskConfigIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantRiskConfigOut:
    """
    Create or replace the tenant-level risk config.

    Domain weights must be between 0.0 and 1.0.
    Keyword suppressions reduce false-positive rates for domains where
    benign terms share vocabulary with risk signals (e.g. 'fail-safe').
    """
    # Validate domains are known MIT domains
    for domain in list(payload.domain_weights.keys()) + list(payload.keyword_suppressions.keys()):
        if domain not in MIT_DOMAINS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown domain: '{domain}'. Valid domains: {MIT_DOMAINS}",
            )

    cfg = db.query(TenantRiskConfig).filter(
        TenantRiskConfig.tenant_id == current_user.tenant_id
    ).first()

    if cfg:
        cfg.domain_weights = payload.domain_weights
        cfg.keyword_suppressions = payload.keyword_suppressions
        cfg.updated_at = datetime.now(tz=timezone.utc)
        logger.info("Risk config updated for tenant %s by %s", current_user.tenant_id, current_user.email)
    else:
        cfg = TenantRiskConfig(
            tenant_id=current_user.tenant_id,
            domain_weights=payload.domain_weights,
            keyword_suppressions=payload.keyword_suppressions,
        )
        db.add(cfg)
        logger.info("Risk config created for tenant %s by %s", current_user.tenant_id, current_user.email)

    db.commit()
    db.refresh(cfg)
    return TenantRiskConfigOut.model_validate(cfg)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_require_risk_config_writer)],
    summary="Reset tenant risk configuration to defaults (super_admin or Risk Officer)",
)
def delete_risk_config(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Remove the tenant's custom risk config, reverting to engine defaults."""
    cfg = db.query(TenantRiskConfig).filter(
        TenantRiskConfig.tenant_id == current_user.tenant_id
    ).first()
    if cfg:
        db.delete(cfg)
        db.commit()
        logger.info("Risk config deleted for tenant %s by %s", current_user.tenant_id, current_user.email)
