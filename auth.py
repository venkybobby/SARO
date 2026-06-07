"""
JWT-based authentication and RBAC for SARO.

Roles:
  super_admin — provisions tenants, manages users, configures defaults.
  operator    — submits batches, runs audits, views reports.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt as _bcrypt_lib
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import User

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# Lazy helpers — read env vars at call time, not import time.
# This prevents KeyError crashes during Koyeb startup before secrets are injected.

def _secret_key() -> str:
    key = os.environ.get("JWT_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not set. "
            "Add it as a Koyeb secret or set it in your .env file."
        )
    return key


def _algorithm() -> str:
    return os.environ.get("JWT_ALGORITHM", "HS256")


def _expire_minutes() -> int:
    return int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))


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


def create_access_token(user: User) -> str:
    """Create a signed JWT containing user identity and role."""
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=_expire_minutes())
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
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
    # Synthesise a transient User-like object so get_current_user returns without a DB hit.
    # The synthetic user is never persisted — it only exists for the lifetime of the request.
    if payload.get("role") == "demo_viewer":
        import uuid as _uuid
        synthetic = User.__new__(User)
        synthetic.id = _uuid.UUID(user_id)
        synthetic.tenant_id = _uuid.UUID(payload.get("tenant_id", user_id))
        synthetic.email = "demo@saro-demo.internal"
        synthetic.role = "demo_viewer"
        synthetic.persona_role = "compliance_lead"
        synthetic.is_active = True
        synthetic.read_only = True  # type: ignore[attr-defined]
        synthetic.hashed_password = ""
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


def require_role(*roles: str):
    """
    Factory that returns a FastAPI dependency enforcing one of the given roles.

    Usage:
        @router.post("/admin/...", dependencies=[Depends(require_role("super_admin"))])
    """

    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
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
    ) -> User:
        persona_role = getattr(current_user, "persona_role", None) or ""
        if persona_role not in personas:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Persona {persona_role!r} is not authorised for this endpoint. "
                       f"Required: {list(personas)}",
            )
        return current_user

    return _check


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the User if credentials are valid, else None."""
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.warning("Login attempt for unknown email: %s", email)
        return None
    if not verify_password(password, user.hashed_password):
        # Log the hash prefix (first 7 chars) to help diagnose hash-format issues
        # without exposing sensitive data.
        prefix = user.hashed_password[:7] if user.hashed_password else "(empty)"
        logger.warning(
            "Login failed for %s — password mismatch (hash prefix: %s)", email, prefix
        )
        return None
    return user
