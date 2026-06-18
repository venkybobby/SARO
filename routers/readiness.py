"""CHUB-004: Compliance Hub readiness checklist API.

    GET  /api/v1/compliance/readiness             — tenant's checklist (manual + derived)
    PUT  /api/v1/compliance/readiness/{item_key}  — toggle a manual item (persisted)

Tenant is always derived from the authenticated user's token; no tenant_id is
accepted from the client. Reads are open to the buyer personas that land on the
Compliance Hub; writes require a write-eligible persona (read-only demo blocked).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user, require_role_or_persona, require_write_persona
from database import get_db
from models import User
from services.readiness_service import get_readiness, set_readiness

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance-readiness"])

_READ_ROLES = ("super_admin", "operator", "demo_viewer")
_READ_PERSONAS = ("compliance_lead", "risk_officer", "admin")


class ReadinessUpdate(BaseModel):
    completed: bool


@router.get(
    "/readiness",
    dependencies=[
        Depends(require_role_or_persona(roles=_READ_ROLES, personas=_READ_PERSONAS))
    ],
    summary="Get the readiness checklist for the current tenant",
)
async def get_readiness_checklist(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    items = get_readiness(db, current_user.tenant_id)
    completed = sum(1 for it in items if it["completed"] is True)
    return {"items": items, "completed": completed, "total": len(items)}


@router.put(
    "/readiness/{item_key}",
    dependencies=[Depends(require_write_persona)],
    summary="Toggle a manual readiness item for the current tenant (persisted)",
)
async def update_readiness_item(
    item_key: str,
    body: ReadinessUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    try:
        return set_readiness(db, current_user.tenant_id, item_key, body.completed)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
