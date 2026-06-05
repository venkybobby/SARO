"""
AI System Inventory service (SAR-013).

Computes audit_status from last_audit_date — NOT stored in DB.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_AUDIT_THRESHOLD_DAYS = 30


def compute_audit_status(
    last_audit_date: Optional[datetime],
    threshold_days: int = _DEFAULT_AUDIT_THRESHOLD_DAYS,
) -> str:
    """
    Compute audit status from last_audit_date.
    Returns: 'current' | 'overdue' | 'never_audited'
    """
    if last_audit_date is None:
        return "never_audited"
    now = datetime.now(timezone.utc)
    if last_audit_date.tzinfo is None:
        last_audit_date = last_audit_date.replace(tzinfo=timezone.utc)
    days_since = (now - last_audit_date).days
    return "current" if days_since <= threshold_days else "overdue"


def system_to_dict(system, audits: list | None = None) -> dict:
    """Serialise an AISystem ORM object to a response dict with computed audit_status."""
    return {
        "id": str(system.id),
        "tenant_id": str(system.tenant_id),
        "name": system.name,
        "description": system.description,
        "system_owner": system.system_owner,
        "purpose": system.purpose,
        "deployment_context": system.deployment_context,
        "eu_ai_act_risk_tier": system.eu_ai_act_risk_tier,
        "last_audit_date": system.last_audit_date.isoformat() if system.last_audit_date else None,
        "current_risk_score": system.current_risk_score,
        "audit_status": compute_audit_status(system.last_audit_date),
        "is_active": system.is_active,
        "created_at": system.created_at.isoformat() if system.created_at else None,
        "linked_audits": [{"audit_id": str(a.audit_id)} for a in (audits or [])],
    }
