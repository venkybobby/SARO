"""
JWT-based authentication and RBAC for SARO.

Roles:
  super_admin — provisions tenants, manages users, configures defaults.
  operator    — submits batches, runs audits, views reports.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt_lib
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# Lazy helpers — read settings at call time, not import time.
# This prevents KeyError crashes during Koyeb startup before secrets are injected.

def _secret_key() -> str:
    key = settings.jwt_secret_key
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not set. "
            "Add it as a Koyeb secret or set it in your .env file."
        )
    return key


def _algorithm() -> str:
    return settings.jwt_algorithm


def _expire_minutes() -> int:
    return settings.access_token_expire_minutes


# ── Password hashing (Argon2id) ───────────────────────────────────────────────
# Using argon2-cffi directly instead of passlib[bcrypt].
#
# Rationale: passlib is effectively abandoned (last release 2020) and is
# incompatible with bcrypt ≥ 4.0 — passlib's internal detect_wrap_bug() self-test
# tries to hash a >72-byte password, which bcrypt 4.x rejects with ValueError
# instead of silently truncating. This causes a 500 on every login attempt.
#
# Argon2id advantages over bcrypt:
#   • No 72-byte password truncation limit (bcrypt algorithm constraint)
#   • OWASP-recommended and Password Hashing Competition winner
#   • Actively maintained library (argon2-cffi)
#   • Memory-hard: more resistant to GPU/ASIC brute-force attacks
#
# Migration: if the database contains legacy bcrypt hashes (hashes starting
# with $2b$ / $2a$) created before this change, verify_password transparently
# falls back to bcrypt.checkpw() so existing accounts keep working without
# any data migration step.

_ph = PasswordHasher()  # default: time_cost=3, memory_cost=65536, parallelism=4
_bearer = HTTPBearer(auto_error=True)

# bcrypt hash prefixes — bcrypt 2a/2b/2y are all valid
_BCRYPT_PREFIXES = ("$2b$", "$2a$", "$2y$")


# ── Password helpers ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Hash a plain-text password using Argon2id (new accounts)."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Supports two hash formats transparently:
    • Argon2id  ($argon2id$...)  — current standard, created by hash_password()
    • bcrypt    ($2b$/2a$/2y$…)  — legacy format; created by passlib before the
                                   Argon2 migration; verified via bcrypt directly

    Always returns False on any mismatch or error; never raises.
    """
    if not hashed:
        return False

    if hashed.startswith(_BCRYPT_PREFIXES):
        # Legacy bcrypt hash: fall back to bcrypt.checkpw()
        try:
            return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception as exc:
            logger.debug("bcrypt verify error (treating as mismatch): %s", exc)
            return False

    # Current Argon2id hash
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.debug("argon2 verify error (treating as mismatch): %s", exc)
        return False


# ── Token helpers ─────────────────────────────────────────────────────────────


def create_access_token(user: User, expire_minutes: int | None = None) -> str:
    """Create a signed JWT containing user identity and role.

    Args:
        user: authenticated User ORM object or SimpleNamespace (demo viewer).
        expire_minutes: per-tenant session length override. When None, falls
            back to the ACCESS_TOKEN_EXPIRE_MINUTES env var (default 480 = 8h).
    """
    minutes = expire_minutes if expire_minutes is not None else _expire_minutes()
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "persona_role": getattr(user, "persona_role", None),
        "tenant_id": str(user.tenant_id),
        "exp": expire,
    }
    return jwt.encode(payload, _secret_key(), algorithm=_algorithm())


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret_key(), algorithms=[_algorithm()])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── FastAPI dependencies ───────────────────────────────────────────────────────


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Validate the Bearer token and return the authenticated User row.

    Raises 401 if the token is invalid/expired, 403 if the user is inactive.
    """
    payload = _decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    # S-205: Demo tokens carry role="demo_viewer" and sub=tenant_id (not a user UUID).
    # Synthesise a transient namespace object so get_current_user returns without a DB hit.
    # We use SimpleNamespace so SQLAlchemy's ORM instrumentation is never involved.
    if payload.get("role") == "demo_viewer":
        import uuid as _uuid
        from types import SimpleNamespace
        synthetic = SimpleNamespace(
            id=_uuid.UUID(user_id),
            tenant_id=_uuid.UUID(payload.get("tenant_id", user_id)),
            email="demo@saro-demo.internal",
            role="demo_viewer",
            persona_role="compliance_lead",
            is_active=True,
            read_only=True,
            hashed_password="",
        )
        return synthetic  # type: ignore[return-value]

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    # GAP-004: propagate JWT-only claims onto the transient user object so
    # downstream dependencies (e.g. require_write_access in demo router) can
    # inspect them without touching the database.
    user.read_only = bool(payload.get("read_only", False))  # type: ignore[attr-defined]
    return user


async def require_write_access(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency: reject requests carrying a read-only demo JWT.

    The demo token (issued by GET /api/v1/demo/token) sets read_only=True.
    Attach this dependency to any endpoint that mutates data so that demo
    users cannot write even when their role would otherwise allow it.

    Usage::

        @router.post("/...", dependencies=[Depends(require_write_access)])
    """
    if getattr(current_user, "read_only", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only demo access — write operations not permitted",
        )
    return current_user


# PT-009: personas/roles permitted to MUTATE risk-register and insight state.
# This is an allowlist (not a denylist): any persona not listed — including a
# NULL persona on a non-system role and any future buyer persona — is denied
# write access by default. ai_auditor is a read-only persona and is excluded.
_WRITE_PERSONAS = frozenset({"compliance_lead", "risk_officer", "admin"})
_SYSTEM_WRITE_ROLES = frozenset({"super_admin", "operator"})
_READ_ONLY_PERSONAS = frozenset({"ai_auditor"})


def _log_authz_denial(current_user: User, request: Request | None, *, required: str) -> None:
    """PT-009 NFR: every authz denial is logged with tenant/user/role/persona/endpoint."""
    endpoint = request.url.path if request is not None else "?"
    logger.warning(
        "authz_denied",
        extra={
            "tenant_id": str(getattr(current_user, "tenant_id", "") or ""),
            "user_id": str(getattr(current_user, "id", "") or ""),
            "role": getattr(current_user, "role", None),
            "persona_role": getattr(current_user, "persona_role", None),
            "endpoint": endpoint,
            "required": required,
        },
    )


def require_role(*roles: str):
    """
    Factory that returns a FastAPI dependency enforcing one of the given roles.

    Usage:
        @router.post("/admin/...", dependencies=[Depends(require_role("super_admin"))])
    """

    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
        request: Request = None,  # type: ignore[assignment]  # injected by FastAPI; None on direct calls
    ) -> User:
        if current_user.role not in roles:
            _log_authz_denial(current_user, request, required=f"role:{roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorised for this action. "
                f"Required: {roles}",
            )
        return current_user

    return _check


def persona_required(*personas: str):
    """
    FastAPI dependency that enforces persona_role membership.

    Usage::

        @router.get("/path", dependencies=[Depends(persona_required("compliance_lead", "admin"))])
    """

    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
        request: Request = None,  # type: ignore[assignment]  # injected by FastAPI; None on direct calls
    ) -> User:
        persona_role = getattr(current_user, "persona_role", None) or ""
        if persona_role not in personas:
            _log_authz_denial(current_user, request, required=f"persona:{list(personas)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Persona {persona_role!r} is not authorised for this endpoint. "
                       f"Required: {list(personas)}",
            )
        return current_user

    return _check


# STORY-TRACE-003: roles/personas permitted to READ TRACE evidence — the
# timeline, audit detail and audit list the AI Auditor's screen depends on.
# Read-only: this grants endpoint access, never write capability (mutations must
# still gate on require_write_access / require_write_persona). ai_auditor and
# compliance_lead are the personas whose job is trace inspection.
TRACE_READ_ROLES: tuple[str, ...] = ("super_admin", "operator")
TRACE_READ_PERSONAS: tuple[str, ...] = ("ai_auditor", "compliance_lead")


def require_role_or_persona(roles: tuple[str, ...], personas: tuple[str, ...]):
    """
    Factory returning a FastAPI dependency that admits a user holding ANY of the
    given primary ``role`` values OR any of the given ``persona_role`` values.

    A read-only authorization helper: it grants access to an endpoint, never write
    capability. Mirrors ``routers/reports.py:_require_reports_access`` so backend
    authz and the persona-driven nav agree. Used by STORY-TRACE-003 to let the
    audit/compliance personas read TRACE evidence alongside the legacy roles.
    """
    role_set = frozenset(roles)
    persona_set = frozenset(personas)
def require_role_or_persona(roles: tuple[str, ...], personas: tuple[str, ...]):
    """
    FastAPI dependency factory granting access if the user's *system role* is in
    ``roles`` OR their ``persona_role`` is in ``personas``.

    Read-only composition of :func:`require_role` and :func:`persona_required` for
    endpoints whose audience spans both system roles (e.g. ``demo_viewer``) and
    buyer personas (e.g. ``compliance_lead``). Tenant scoping is unaffected — it is
    enforced inside each handler via ``tenant_id`` filters.

    Usage::

        @router.get(
            "/audits",
            dependencies=[Depends(require_role_or_persona(
                roles=("super_admin", "operator", "demo_viewer"),
                personas=("compliance_lead", "risk_officer", "admin"),
            ))],
        )
    """

    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
        request: Request = None,  # type: ignore[assignment]  # injected by FastAPI; None on direct calls
    ) -> User:
        if current_user.role in role_set:
            return current_user
        if (getattr(current_user, "persona_role", None) or "") in persona_set:
            return current_user
        _log_authz_denial(
            current_user,
            request,
            required=f"role:{sorted(role_set)}|persona:{sorted(persona_set)}",
        )
        # Generic message — do not echo role/persona identifiers to the client.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to read this resource.",
        if current_user.role in roles:
            return current_user
        if (getattr(current_user, "persona_role", None) or "") in personas:
            return current_user
        _log_authz_denial(
            current_user, request, required=f"role:{roles}|persona:{personas}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{current_user.role}' / persona "
                f"'{getattr(current_user, 'persona_role', None)}' is not authorised "
                f"for this action. Required role {roles} or persona {personas}."
            ),
        )

    return _check


async def require_write_persona(
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request = None,  # type: ignore[assignment]  # injected by FastAPI; None on direct calls
) -> User:
    """
    PT-009 (FND-009): allowlist write-guard for risk-register / insight mutations.

    Denies read-only demo tokens, the read-only ``ai_auditor`` persona, and any
    persona not explicitly granted write access (NULL or future personas default
    to deny). System roles (super_admin / operator) without a buyer persona are
    permitted because they legitimately operate the platform. Every denial is logged.
    """
    if getattr(current_user, "read_only", False):
        _log_authz_denial(current_user, request, required="write:not-read-only")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only access — write operations not permitted",
        )
    persona = getattr(current_user, "persona_role", None) or ""
    role = getattr(current_user, "role", None) or ""
    if persona in _WRITE_PERSONAS or role in _SYSTEM_WRITE_ROLES:
        return current_user
    _log_authz_denial(current_user, request, required=f"write-persona:{sorted(_WRITE_PERSONAS)}")
    detail = (
        "Read-only persona: this account may view but not modify this resource."
        if persona in _READ_ONLY_PERSONAS
        else f"Persona {persona!r} is not authorised to modify this resource."
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the User if credentials are valid, else None."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.warning("Login attempt for unknown email: %s", email)
        return None
    if not verify_password(password, user.hashed_password or ""):
        # Log the hash prefix (first 7 chars) to help diagnose hash-format issues
        # without exposing sensitive data.
        prefix = user.hashed_password[:7] if user.hashed_password else "(empty)"
        logger.warning(
            "Login failed for %s — password mismatch (hash prefix: %s)", email, prefix
        )
        return None
    return user
