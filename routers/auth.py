"""
Authentication routes.

POST /api/v1/auth/token     — login → JWT
POST /api/v1/auth/register  — super_admin creates a new user
GET  /api/v1/auth/me        — current user info
POST /api/v1/tenants        — super_admin creates a tenant
GET  /api/v1/tenants        — super_admin lists tenants
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
)
from database import get_db
from models import PersonaPermission, Tenant, User
from schemas import (
    BootstrapIn,
    LoginIn,
    TenantCreateIn,
    TenantOut,
    TokenOut,
    UserCreateIn,
    UserOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
tenants_router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("/bootstrap", status_code=201)
def bootstrap(
    payload: BootstrapIn,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    One-time first-run bootstrap: create the initial tenant + super_admin.

    Succeeds only when the users table is completely empty.
    After the first call this endpoint always returns 409 — use
    POST /api/v1/auth/token to log in with the account created here.
    """
    if db.query(User).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap already completed — at least one user exists. "
                   "Use POST /api/v1/auth/token to log in.",
        )
    # Derive a URL-safe slug from org_name
    slug = payload.org_name.lower().replace(" ", "-").replace("_", "-")
    # Ensure slug uniqueness (in case bootstrap is somehow called in a race)
    existing_tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing_tenant:
        slug = f"{slug}-{str(existing_tenant.id)[:4]}"

    tenant = Tenant(name=payload.org_name, slug=slug)
    db.add(tenant)
    db.flush()  # populate tenant.id without committing

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="super_admin",
        tenant_id=tenant.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "Bootstrap complete: tenant=%s (%s), super_admin=%s",
        tenant.name, str(tenant.id), user.email,
    )
    return {
        "message": f"Bootstrap complete. Login with {payload.email}",
        "tenant_id": str(tenant.id),
        "user_id": str(user.id),
    }


@router.post("/token", response_model=TokenOut)
def login(payload: LoginIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    """Exchange email + password for a JWT access token."""
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user)
    logger.info("User %s logged in (role=%s)", user.email, user.role)
    return TokenOut(access_token=token)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
)
def register_user(
    payload: UserCreateIn,
    db: Annotated[Session, Depends(get_db)],
    _current: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    """Super admin creates a new user within a tenant."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email {payload.email!r} is already registered",
        )
    tenant = db.get(Tenant, payload.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {payload.tenant_id} not found",
        )
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        tenant_id=payload.tenant_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created user %s (role=%s, tenant=%s)", user.email, user.role, user.tenant_id)
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
def me(
    current: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserOut:
    """Return the authenticated user with persona_role and tab permissions (CF-06)."""
    out = UserOut.model_validate(current)
    if current.persona_role:
        perm = (
            db.query(PersonaPermission)
            .filter(PersonaPermission.persona_role == current.persona_role)
            .first()
        )
        if perm:
            out.allowed_tabs = perm.allowed_tabs or []
            out.allowed_actions = perm.allowed_actions or []
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Tenant management (super_admin only)
# ─────────────────────────────────────────────────────────────────────────────


@tenants_router.post(
    "",
    response_model=TenantOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
)
def create_tenant(
    payload: TenantCreateIn,
    db: Annotated[Session, Depends(get_db)],
    _current: Annotated[User, Depends(get_current_user)],
) -> TenantOut:
    """Provision a new tenant (super_admin only)."""
    existing = db.query(Tenant).filter(Tenant.slug == payload.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant slug {payload.slug!r} already exists",
        )
    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    logger.info("Provisioned tenant %s (%s)", tenant.name, tenant.slug)
    return TenantOut.model_validate(tenant)


@tenants_router.get(
    "",
    response_model=list[TenantOut],
    dependencies=[Depends(require_role("super_admin"))],
)
def list_tenants(
    db: Annotated[Session, Depends(get_db)],
    _current: Annotated[User, Depends(get_current_user)],
) -> list[TenantOut]:
    """List all tenants (super_admin only)."""
    return [TenantOut.model_validate(t) for t in db.query(Tenant).all()]


# ── Persona assignment ────────────────────────────────────────────────────────

_VALID_PERSONAS = {"compliance_lead", "risk_officer", "ai_auditor", "admin"}


@router.patch("/users/{user_id}/persona", response_model=UserOut)
def set_user_persona(
    user_id: uuid.UUID,
    persona_role: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    """Set a user's persona role. Requires super_admin."""
    if current.role != "super_admin":
        raise HTTPException(status_code=403, detail="super_admin required")
    if persona_role not in _VALID_PERSONAS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid persona. Must be one of: {sorted(_VALID_PERSONAS)}",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.persona_role = persona_role
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
