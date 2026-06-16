"""STORY-301 — AI system & agent registry API.

CRUD for the GRC registry. Every create/update writes an immutable audit-trail
row (handled in :mod:`grc.registry`). All reads/writes are tenant-scoped via the
authenticated user's ``tenant_id``.

    POST   /api/v1/grc/registry             — create an entry
    GET    /api/v1/grc/registry             — list + filter (tier/owner/lifecycle)
    GET    /api/v1/grc/registry/{id}        — retrieve by id
    PATCH  /api/v1/grc/registry/{id}        — update (records a diff)
    GET    /api/v1/grc/registry/{id}/audit  — the entry's audit trail
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_write_access
from database import get_db
from grc import registry as registry_svc
from grc.registry import (
    RegistryEntryCreate,
    RegistryEntryOut,
    RegistryEntryUpdate,
)
from models import GRCRegistryAudit, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/grc/registry", tags=["grc-registry"])


@router.post("", response_model=RegistryEntryOut, status_code=status.HTTP_201_CREATED)
async def create_registry_entry(
    payload: RegistryEntryCreate,
    current_user: Annotated[User, Depends(require_write_access)],
    db: Annotated[Session, Depends(get_db)],
) -> RegistryEntryOut:
    """Create an AI system/agent entry. ``owner`` must be a named human."""
    entry = registry_svc.create_entry(
        db, tenant_id=current_user.tenant_id, payload=payload, actor=current_user
    )
    return RegistryEntryOut.model_validate(entry)


@router.get("", response_model=list[RegistryEntryOut])
async def list_registry_entries(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tier: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
    lifecycle_stage: Annotated[str | None, Query()] = None,
) -> list[RegistryEntryOut]:
    """List the tenant's entries, optionally filtered by tier/owner/lifecycle."""
    entries = registry_svc.list_entries(
        db,
        tenant_id=current_user.tenant_id,
        tier=tier,
        owner=owner,
        lifecycle_stage=lifecycle_stage,
    )
    return [RegistryEntryOut.model_validate(e) for e in entries]


@router.get("/{entry_id}", response_model=RegistryEntryOut)
async def get_registry_entry(
    entry_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RegistryEntryOut:
    entry = registry_svc.get_entry(
        db, tenant_id=current_user.tenant_id, entry_id=entry_id
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="entry not found"
        )
    return RegistryEntryOut.model_validate(entry)


@router.patch("/{entry_id}", response_model=RegistryEntryOut)
async def update_registry_entry(
    entry_id: uuid.UUID,
    payload: RegistryEntryUpdate,
    current_user: Annotated[User, Depends(require_write_access)],
    db: Annotated[Session, Depends(get_db)],
) -> RegistryEntryOut:
    entry = registry_svc.get_entry(
        db, tenant_id=current_user.tenant_id, entry_id=entry_id
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="entry not found"
        )
    entry = registry_svc.update_entry(
        db, entry=entry, payload=payload, actor=current_user
    )
    return RegistryEntryOut.model_validate(entry)


@router.get("/{entry_id}/audit")
async def get_registry_entry_audit(
    entry_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """Return the immutable audit trail for one entry (who/what/when)."""
    rows = (
        db.query(GRCRegistryAudit)
        .filter(
            GRCRegistryAudit.entry_id == entry_id,
            GRCRegistryAudit.tenant_id == current_user.tenant_id,
        )
        .order_by(GRCRegistryAudit.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "action": r.action,
            "actor_email": r.actor_email,
            "changes": r.changes_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
