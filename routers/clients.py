"""
Enterprise Client Onboarding & Identity Management routes.

POST /api/v1/clients                        — provision new client (super_admin only)
GET  /api/v1/clients                        — list all clients
GET  /api/v1/clients/{tenant_id}            — client detail
POST /api/v1/clients/{tenant_id}/test-sso   — validate SSO configuration
POST /api/v1/clients/{tenant_id}/scim/rotate-token — rotate SCIM bearer token
GET  /api/v1/audit-events                   — immutable event log (super_admin only)
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import get_current_user, hash_password, require_role, require_write_access
from database import get_db
from models import AuditEvent, ClientConfig, Tenant, User
from schemas import (
    AuditEventOut,
    ClientConfigOut,
    ClientOnboardingIn,
    SCIMTokenRotateOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])
audit_events_router = APIRouter(prefix="/api/v1/audit-events", tags=["audit-events"])

_SARO_API_URL = os.environ.get("SARO_API_URL", "http://localhost:8000").rstrip("/")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log_event(
    db: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    event_type: str,
    event_data: dict[str, Any],
) -> None:
    """Append an immutable audit event record."""
    evt = AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        event_data=event_data,
    )
    db.add(evt)
    # Intentionally not committing here — caller controls the transaction


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _scim_endpoint_url(tenant_id: uuid.UUID) -> str:
    return f"{_SARO_API_URL}/scim/v2/{tenant_id}"


def _build_client_out(
    tenant: Tenant,
    cfg: ClientConfig,
    users_enrolled: int = 0,
    scim_bearer_token: str | None = None,
) -> ClientConfigOut:
    return ClientConfigOut(
        tenant_id=tenant.id,
        company_name=tenant.name,
        slug=tenant.slug,
        industry=cfg.industry,
        size=cfg.size,
        primary_contact_name=cfg.primary_contact_name,
        primary_contact_email=cfg.primary_contact_email,
        sso_enabled=cfg.sso_enabled,
        idp_provider=cfg.idp_provider,
        scim_enabled=cfg.scim_enabled,
        scim_endpoint=cfg.scim_endpoint,
        scim_bearer_token=scim_bearer_token,
        mfa_required=cfg.mfa_required,
        allow_magic_link_fallback=cfg.allow_magic_link_fallback,
        users_enrolled=users_enrolled,
        created_at=cfg.created_at,
    )


def _get_client_or_404(tenant_id: uuid.UUID, db: Session) -> tuple[Tenant, ClientConfig]:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Client not found")
    cfg = db.query(ClientConfig).filter(ClientConfig.tenant_id == tenant_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Client configuration not found")
    return tenant, cfg


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ClientConfigOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Provision a new enterprise client with SSO/SCIM configuration",
)
def create_client(
    payload: ClientOnboardingIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ClientConfigOut:
    """
    Enterprise client onboarding.

    Creates a Tenant record, attaches full SSO/SCIM/MFA configuration,
    optionally provisions initial users, and writes an immutable audit event.
    Returns the SCIM bearer token in plaintext exactly once — store it now.
    """
    # Uniqueness check on company name
    existing = db.query(Tenant).filter(Tenant.name == payload.company_name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A client named '{payload.company_name}' already exists.",
        )

    # Derive slug from company name
    slug_base = payload.company_name.lower().replace(" ", "-").replace("_", "-")
    # Strip non-alphanumeric-hyphen chars
    slug_base = "".join(c for c in slug_base if c.isalnum() or c == "-")
    slug = slug_base
    n = 1
    while db.query(Tenant).filter(Tenant.slug == slug).first():
        slug = f"{slug_base}-{n}"
        n += 1

    # Create Tenant
    tenant = Tenant(name=payload.company_name, slug=slug)
    db.add(tenant)
    db.flush()  # populate tenant.id

    # Build IDP metadata JSON
    idp_metadata: dict[str, Any] | None = None
    idp_provider: str | None = None
    if payload.sso_enabled and payload.idp_config:
        idp_provider = payload.idp_config.provider
        idp_metadata = {
            "provider": payload.idp_config.provider,
            "entity_id": payload.idp_config.entity_id,
            "sso_url": payload.idp_config.sso_url,
            "metadata_url": payload.idp_config.metadata_url,
            "tenant_domain": payload.idp_config.tenant_domain,
            # Certificate and client_secret are present/absent flags only (never stored in plaintext)
            "has_certificate": bool(payload.idp_config.certificate),
            "has_client_secret": bool(payload.idp_config.client_secret),
            **payload.idp_config.extra,
        }

    # SCIM token (generated once, stored as hash)
    scim_token_plaintext: str | None = None
    scim_endpoint: str | None = None
    scim_token_hash: str | None = None
    if payload.scim_enabled:
        scim_token_plaintext = secrets.token_urlsafe(32)
        scim_token_hash = _hash_token(scim_token_plaintext)
        scim_endpoint = _scim_endpoint_url(tenant.id)

    # Create ClientConfig
    cfg = ClientConfig(
        tenant_id=tenant.id,
        industry=payload.industry,
        size=payload.size,
        primary_contact_name=payload.primary_contact_name,
        primary_contact_email=str(payload.primary_contact_email) if payload.primary_contact_email else None,
        sso_enabled=payload.sso_enabled,
        idp_provider=idp_provider,
        idp_metadata=idp_metadata,
        scim_enabled=payload.scim_enabled,
        scim_endpoint=scim_endpoint,
        scim_bearer_token_hash=scim_token_hash,
        mfa_required=payload.mfa_required,
        allow_magic_link_fallback=payload.allow_magic_link_fallback,
    )
    db.add(cfg)

    # Provision initial users
    users_enrolled = 0
    for u_in in payload.initial_users:
        if db.query(User).filter(User.email == str(u_in.email)).first():
            logger.warning("Skipping duplicate email during enrollment: %s", u_in.email)
            continue
        # JIT users get a temporary password; SSO users don't need it
        temp_pw = secrets.token_urlsafe(16) if payload.jit_provisioning_enabled else secrets.token_urlsafe(16)
        new_user = User(
            email=str(u_in.email),
            hashed_password=hash_password(temp_pw),
            role=u_in.role,
            tenant_id=tenant.id,
        )
        db.add(new_user)
        users_enrolled += 1

    # Immutable audit event
    _log_event(
        db,
        tenant.id,
        current_user.id,
        "client_created",
        {
            "company_name": payload.company_name,
            "slug": slug,
            "sso_enabled": payload.sso_enabled,
            "idp_provider": idp_provider,
            "scim_enabled": payload.scim_enabled,
            "mfa_required": payload.mfa_required,
            "users_enrolled": users_enrolled,
            "created_by": current_user.email,
        },
    )
    db.commit()
    db.refresh(cfg)

    logger.info(
        "Client onboarded: %s (tenant=%s, idp=%s, users=%d)",
        payload.company_name, tenant.id, idp_provider, users_enrolled,
    )
    return _build_client_out(tenant, cfg, users_enrolled, scim_token_plaintext)


@router.get(
    "",
    response_model=list[ClientConfigOut],
    dependencies=[Depends(require_role("super_admin"))],
    summary="List all provisioned enterprise clients",
)
def list_clients(
    _current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ClientConfigOut]:
    """Return all tenants that have an associated ClientConfig (enterprise clients)."""
    configs = (
        db.query(ClientConfig)
        .order_by(ClientConfig.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    results = []
    for cfg in configs:
        tenant = db.get(Tenant, cfg.tenant_id)
        if not tenant:
            continue
        user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        results.append(_build_client_out(tenant, cfg, user_count))
    return results


# ── FND-067: tenant security contact ─────────────────────────────────────────
# Registered BEFORE the dynamic /{tenant_id} route (FND-051: FastAPI matches in
# registration order — a later static path would be captured as tenant_id).


class SecurityContactIn(BaseModel):
    security_contact_email: EmailStr


@router.get(
    "/security-contact",
    dependencies=[Depends(require_role("admin", "super_admin"))],
    summary="FND-067: read this tenant's recorded security contact",
)
def get_security_contact(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tenant = db.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "tenant_id": str(tenant.id),
        "security_contact_email": tenant.security_contact_email,
    }


@router.put(
    "/security-contact",
    dependencies=[
        Depends(require_role("admin", "super_admin")),
        Depends(require_write_access),
    ],
    summary="FND-067: set this tenant's security contact (72h breach-notification recipient)",
)
def set_security_contact(
    payload: SecurityContactIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Who receives breach notifications for this tenant
    (docs/ops/breach-notification-template.md; support-model.md §4)."""
    tenant = db.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.security_contact_email = str(payload.security_contact_email)
    # STORY-366 AUDITED promise: use the router's sanctioned recorder helper.
    _log_event(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        event_type="security_contact_updated",
        event_data={"security_contact_email": tenant.security_contact_email},
    )
    db.commit()
    return {
        "tenant_id": str(tenant.id),
        "security_contact_email": tenant.security_contact_email,
    }


@router.get(
    "/{tenant_id}",
    response_model=ClientConfigOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Enterprise client detail",
)
def get_client(
    tenant_id: uuid.UUID,
    _current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ClientConfigOut:
    tenant, cfg = _get_client_or_404(tenant_id, db)
    user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
    return _build_client_out(tenant, cfg, user_count)


@router.post(
    "/{tenant_id}/test-sso",
    dependencies=[Depends(require_role("super_admin"))],
    summary="Validate SSO configuration — live connection test",
)
def test_sso_connection(
    tenant_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """
    Validates the IDP configuration for this client.

    For metadata-URL-based configs, attempts to fetch the metadata document.
    For manually configured providers, validates field completeness.
    Writes a sso_test_passed / sso_test_failed audit event.
    """
    tenant, cfg = _get_client_or_404(tenant_id, db)

    if not cfg.sso_enabled:
        raise HTTPException(status_code=400, detail="SSO is not enabled for this client.")
    if not cfg.idp_metadata:
        raise HTTPException(status_code=400, detail="No IDP configuration found. Save SSO settings first.")

    meta = cfg.idp_metadata
    passed = False
    details: dict[str, Any] = {"provider": meta.get("provider")}
    errors: list[str] = []

    # Attempt metadata URL fetch
    metadata_url = meta.get("metadata_url")
    if metadata_url:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(metadata_url)
            if resp.status_code == 200:
                passed = True
                details["metadata_url_status"] = resp.status_code
                details["metadata_fetched"] = True
            else:
                errors.append(f"Metadata URL returned HTTP {resp.status_code}")
        except httpx.TimeoutException:
            errors.append("Metadata URL fetch timed out (10 s)")
        except Exception as exc:
            errors.append(f"Metadata URL fetch failed: {exc}")
    else:
        # Validate field completeness per provider
        provider = meta.get("provider", "")
        required_fields: dict[str, list[str]] = {
            "okta": ["entity_id", "sso_url", "has_certificate"],
            "azure_ad": ["entity_id", "sso_url", "tenant_domain"],
            "google_workspace": ["entity_id", "sso_url", "tenant_domain"],
            "pingfederate": ["entity_id", "sso_url", "has_certificate"],
            "custom_saml": ["entity_id", "sso_url", "has_certificate"],
            "custom_oidc": ["entity_id", "sso_url", "has_client_secret"],
        }
        for field in required_fields.get(provider, []):
            val = meta.get(field)
            if not val:
                errors.append(f"Missing required field: {field}")
        passed = len(errors) == 0
        details["field_validation"] = "passed" if passed else "failed"

    event_type = "sso_test_passed" if passed else "sso_test_failed"
    _log_event(db, tenant_id, current_user.id, event_type, {**details, "errors": errors})
    db.commit()

    if passed:
        return {"status": "success", "message": "SSO connection validated successfully.", "details": details}
    return {
        "status": "error",
        "message": "SSO validation failed. Review errors and retry.",
        "errors": errors,
        "details": details,
    }


@router.post(
    "/{tenant_id}/scim/rotate-token",
    response_model=SCIMTokenRotateOut,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Rotate SCIM 2.0 bearer token — shown once, store it now",
)
def rotate_scim_token(
    tenant_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SCIMTokenRotateOut:
    """Generate a new SCIM bearer token. The previous token is immediately invalidated."""
    tenant, cfg = _get_client_or_404(tenant_id, db)

    new_token = secrets.token_urlsafe(32)
    cfg.scim_bearer_token_hash = _hash_token(new_token)
    cfg.scim_enabled = True
    if not cfg.scim_endpoint:
        cfg.scim_endpoint = _scim_endpoint_url(tenant_id)
    cfg.updated_at = datetime.now(tz=timezone.utc)

    _log_event(db, tenant_id, current_user.id, "scim_token_rotated", {
        "scim_endpoint": cfg.scim_endpoint,
        "rotated_by": current_user.email,
    })
    db.commit()
    db.refresh(cfg)

    logger.info("SCIM token rotated for tenant %s by %s", tenant_id, current_user.email)
    return SCIMTokenRotateOut(scim_endpoint=cfg.scim_endpoint, bearer_token=new_token)


# ── Audit Events ──────────────────────────────────────────────────────────────


@audit_events_router.get(
    "",
    response_model=list[AuditEventOut],
    dependencies=[Depends(require_role("super_admin"))],
    summary="Immutable audit event log (append-only)",
)
def list_audit_events(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tenant_id: uuid.UUID | None = Query(default=None, description="Filter by tenant"),
    event_type: str | None = Query(default=None, description="Filter by event type"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEventOut]:
    """Return the immutable audit event log. Super-admin sees all tenants."""
    q = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if tenant_id:
        q = q.filter(AuditEvent.tenant_id == tenant_id)
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)
    events = q.offset(offset).limit(limit).all()
    return [AuditEventOut.model_validate(e) for e in events]
