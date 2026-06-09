"""
Onboarding Status API
=====================
GET /api/v1/onboarding/status?tenant_id=<uuid>

Returns a structured onboarding completion checklist for the authenticated
tenant.  The React frontend calls this on first load to guide new tenants
through the setup flow (profile, first scan, integrations, etc.).
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import AIMSDocument, Audit, ClientConfig, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


def _step(key: str, label: str, done: bool, cta_url: str | None = None) -> dict:
    return {"key": key, "label": label, "completed": done, "cta_url": cta_url}


@router.get(
    "/status",
    summary="Return onboarding completion checklist for the tenant",
)
def get_onboarding_status(
    tenant_id: str | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
) -> dict:
    """
    Structured onboarding checklist consumed by the React frontend setup flow.

    ``tenant_id`` query param is accepted for frontend compatibility; the
    effective tenant is always derived from the authenticated JWT.
    """
    effective_tenant = current_user.tenant_id

    # ── gather completion signals ──────────────────────────────────────────
    has_first_audit = (
        db.query(Audit)
        .filter(Audit.tenant_id == effective_tenant)
        .first()
    ) is not None

    has_aims_doc = (
        db.query(AIMSDocument)
        .filter(AIMSDocument.tenant_id == effective_tenant)
        .first()
    ) is not None

    cfg: ClientConfig | None = (
        db.query(ClientConfig)
        .filter(ClientConfig.tenant_id == effective_tenant)
        .first()
    )
    profile_complete = cfg is not None
    sso_configured = bool(cfg and getattr(cfg, "sso_enabled", False)) if cfg else False

    steps = [
        _step(
            "profile",
            "Complete tenant profile",
            profile_complete,
            "/api/v1/clients/me",
        ),
        _step(
            "first_scan",
            "Run your first risk scan",
            has_first_audit,
            "/api/v1/scan",
        ),
        _step(
            "aims_doc",
            "Register an AI model in the AIMS document library",
            has_aims_doc,
            "/api/v1/aims/documents",
        ),
        _step(
            "sso",
            "Configure SAML 2.0 SSO (optional)",
            sso_configured,
            "/api/v1/sso/configure",
        ),
    ]

    completed = sum(1 for s in steps if s["completed"])
    pct = round((completed / len(steps)) * 100)

    return {
        "tenant_id": str(effective_tenant),
        "completed_steps": completed,
        "total_steps": len(steps),
        "completion_pct": pct,
        "onboarding_complete": pct == 100,
        "steps": steps,
    }
