"""
AI System Inventory router (SAR-013).

GET  /api/v1/systems              — list all systems for tenant
POST /api/v1/systems              — create a system
PATCH /api/v1/systems/{id}        — update (eu_ai_act_risk_tier restricted to compliance_lead/risk_officer)
GET  /api/v1/systems/{id}/audits  — list audit history for a system
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import AISystem, SystemAudit, User
from services.system_service import system_to_dict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/systems", tags=["systems"])

_RISK_TIERS = {"unacceptable", "high", "limited", "minimal"}
# CRITICAL: only these personas may set eu_ai_act_risk_tier (EU AI Act Art. 14 — human decision only)
_RISK_TIER_PERSONAS = {"compliance_lead", "risk_officer", "admin", "super_admin"}


@router.get("")
def list_systems(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """List all active AI systems for the current tenant."""
    systems = (
        db.query(AISystem)
        .filter(AISystem.tenant_id == current_user.tenant_id, AISystem.is_active.is_(True))
        .order_by(AISystem.created_at.desc())
        .all()
    )
    return [system_to_dict(s) for s in systems]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_system(
    payload: dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Create a new AI system entry."""
    system = AISystem(
        tenant_id=current_user.tenant_id,
        name=payload.get("name", ""),
        description=payload.get("description"),
        system_owner=payload.get("system_owner"),
        purpose=payload.get("purpose"),
        deployment_context=payload.get("deployment_context"),
        is_active=True,
    )
    db.add(system)
    db.commit()
    db.refresh(system)
    logger.info("AI system created: %s tenant=%s", system.name, current_user.tenant_id)
    return system_to_dict(system)


@router.patch("/{system_id}")
def update_system(
    system_id: uuid.UUID,
    payload: dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Update an AI system.

    CRITICAL: eu_ai_act_risk_tier is a HUMAN governance decision per EU AI Act Art. 14.
    Only compliance_lead and risk_officer personas may set this field.
    The audit engine MUST NEVER call this endpoint to set eu_ai_act_risk_tier.
    """
    system = db.query(AISystem).filter(
        AISystem.id == system_id,
        AISystem.tenant_id == current_user.tenant_id,
    ).first()
    if not system:
        raise HTTPException(status_code=404, detail="AI system not found")

    # Risk tier RBAC guard (EU AI Act Art. 14 — human decision only)
    if "eu_ai_act_risk_tier" in payload:
        persona = getattr(current_user, "persona_role", None) or current_user.role
        if persona not in _RISK_TIER_PERSONAS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="eu_ai_act_risk_tier may only be set by compliance_lead or risk_officer. "
                       "This is a human governance decision per EU AI Act Art. 14.",
            )
        tier = payload["eu_ai_act_risk_tier"]
        if tier is not None and tier not in _RISK_TIERS:
            raise HTTPException(status_code=422, detail=f"Invalid risk tier. Must be one of: {sorted(_RISK_TIERS)}")
        system.eu_ai_act_risk_tier = tier

    for field in ("name", "description", "system_owner", "purpose", "deployment_context", "is_active"):
        if field in payload:
            setattr(system, field, payload[field])

    system.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(system)
    return system_to_dict(system)


@router.get("/{system_id}/audits")
def get_system_audits(
    system_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Get all audit records linked to an AI system."""
    system = db.query(AISystem).filter(
        AISystem.id == system_id,
        AISystem.tenant_id == current_user.tenant_id,
    ).first()
    if not system:
        raise HTTPException(status_code=404, detail="AI system not found")

    linked = db.query(SystemAudit).filter(SystemAudit.system_id == system_id).all()
    return system_to_dict(system, audits=linked)
