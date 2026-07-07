"""SARO self-audit query interface (STORY-META-001 AC-4).

Internal, AI-Auditor-facing: filter SARO's own privileged-action audit trail and
verify its per-tenant hash chain. Exporting the trail itself generates an EXPORT
event (self-referential by design).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from auth import get_current_user, require_role_or_persona
from database import get_db
import services.self_audit as sa

router = APIRouter(prefix="/api/v1/audit", tags=["self-audit"])

# Internal audit interface — auditor/operator only.
_require_auditor = require_role_or_persona(("super_admin", "operator"), ("ai_auditor",))
_PRIVILEGED_ROLES = frozenset({"super_admin", "operator"})


def _resolve_tenant(current_user, scope: str) -> uuid.UUID:
    """Tenant to query. 'system' (global rule-pack/out-of-band events) is privileged."""
    if scope == "system":
        if getattr(current_user, "role", None) not in _PRIVILEGED_ROLES:
            raise HTTPException(
                status_code=403, detail="system audit scope requires an operator role"
            )
        return sa.SYSTEM_TENANT_ID
    return current_user.tenant_id


def _serialize(e) -> dict:
    return {
        "id": str(e.id),
        "action_class": e.action_class,
        "actor": e.actor,
        "target_type": e.target_type,
        "target_id": e.target_id,
        "outcome": e.outcome,
        "retroactive": e.retroactive,
        "seq": e.seq,
        "event_hash": e.event_hash,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get(
    "/events",
    dependencies=[Depends(_require_auditor)],
    summary="Query the SARO self-audit trail",
)
def list_audit_events(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    actor: Optional[str] = None,
    action_class: Optional[str] = None,
    target_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    scope: str = Query(default="tenant", description="tenant | system"),
    export: bool = Query(
        default=False, description="Generate an EXPORT event + full artifact"
    ),
):
    tenant_id = _resolve_tenant(current_user, scope)
    events = sa.query_events(
        db,
        tenant_id,
        actor=actor,
        action_class=action_class,
        target_id=target_id,
        since=since,
        until=until,
    )
    result = {
        "scope": scope,
        "count": len(events),
        "events": [_serialize(e) for e in events],
        "chain_verification": sa.verify_audit_chain(db, tenant_id),
    }
    if export:
        # AC-4: the export itself generates an EXPORT event (self-referential).
        sa.record_privileged(
            db,
            tenant_id=tenant_id,
            actor=getattr(current_user, "email", "?"),
            action_class=sa.EXPORT,
            user_id=getattr(current_user, "id", None),
            target_type="audit_trail",
            target_id=scope,
            metadata={"exported_count": len(events)},
        )
        result["export_recorded"] = True
    return result


@router.get(
    "/events/verify",
    dependencies=[Depends(_require_auditor)],
    summary="Verify the audit hash chain",
)
def verify_chain_endpoint(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    scope: str = Query(default="tenant", description="tenant | system"),
):
    tenant_id = _resolve_tenant(current_user, scope)
    return sa.verify_audit_chain(db, tenant_id)
