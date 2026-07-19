"""FND-058 — ensure_demo_user() silently hijacked any user matched by email.

`ensure_demo_user()` (`scripts/seed_demo_tenant.py`) looked up an existing user
by email only (`SELECT id FROM users WHERE email = :email`), then
unconditionally reassigned `tenant_id`, escalated `role` to `'super_admin'`,
and reset the password on any match — with no check that the matched row
already belonged to the demo tenant or already had `role='super_admin'`.
`email` is globally unique (`models.User.email`, `unique=True`), so this is
low-likelihood in practice — it would require the demo email to somehow be
reused by an unrelated real account — and the caller already needs
`DATABASE_URL` access (already the highest privilege) to run this script.
Flagged low-severity, non-blocking, by security-auditor review of PR #119
(branch `fix/seed-demo-tenant-login`).

Fix: before overwriting, if the matched row's `tenant_id` is non-null and
either differs from the target tenant or its `role` isn't already
`'super_admin'`, `ensure_demo_user()` raises instead of silently reassigning
tenant/role/password on what looks like an unrelated account. The legitimate
idempotent-reset path (same tenant, already `super_admin`) is unaffected.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from database import Base  # noqa: E402
from models import Tenant, User  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _make_tenant(db, slug: str) -> Tenant:
    tenant = Tenant(id=uuid.uuid4(), name=slug, slug=slug)
    db.add(tenant)
    db.flush()
    return tenant


def _reset_db(db) -> None:
    db.query(User).delete()
    db.query(Tenant).delete()
    db.commit()


@pytest.mark.regression
def test_refuses_to_hijack_user_belonging_to_a_different_tenant():
    from scripts.seed_demo_tenant import ensure_demo_user

    db = _Session()
    try:
        _reset_db(db)
        real_tenant = _make_tenant(db, f"real-co-{uuid.uuid4().hex[:8]}")
        demo_tenant = _make_tenant(db, f"saro-demo-{uuid.uuid4().hex[:8]}")
        email = "demo@saro-demo.io"
        victim = User(
            id=uuid.uuid4(),
            tenant_id=real_tenant.id,
            email=email,
            hashed_password="unrelated-hash",
            role="operator",
            is_active=True,
        )
        db.add(victim)
        db.commit()

        with pytest.raises(RuntimeError):
            ensure_demo_user(db, str(demo_tenant.id), email, "new-demo-pw")

        db.expire_all()
        reloaded = db.get(User, victim.id)
        assert reloaded.tenant_id == real_tenant.id, (
            "must not reassign tenant_id of an unrelated account (FND-058)"
        )
        assert reloaded.role == "operator", (
            "must not escalate role of an unrelated account (FND-058)"
        )
        assert reloaded.hashed_password == "unrelated-hash", (
            "must not reset the password of an unrelated account (FND-058)"
        )
    finally:
        db.close()


@pytest.mark.regression
def test_refuses_to_escalate_role_of_same_tenant_non_admin_user():
    from scripts.seed_demo_tenant import ensure_demo_user

    db = _Session()
    try:
        _reset_db(db)
        tenant = _make_tenant(db, f"saro-demo-{uuid.uuid4().hex[:8]}")
        email = "demo@saro-demo.io"
        victim = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password="unrelated-hash",
            role="operator",
            is_active=True,
        )
        db.add(victim)
        db.commit()

        with pytest.raises(RuntimeError):
            ensure_demo_user(db, str(tenant.id), email, "new-demo-pw")

        db.expire_all()
        reloaded = db.get(User, victim.id)
        assert reloaded.role == "operator", (
            "must not escalate role of a non-admin user in the target tenant (FND-058)"
        )
        assert reloaded.hashed_password == "unrelated-hash"
    finally:
        db.close()


@pytest.mark.regression
def test_legitimate_reset_still_succeeds_for_matching_tenant_and_role():
    from scripts.seed_demo_tenant import ensure_demo_user

    db = _Session()
    try:
        _reset_db(db)
        tenant = _make_tenant(db, f"saro-demo-{uuid.uuid4().hex[:8]}")
        email = "demo@saro-demo.io"
        existing = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            hashed_password="old-hash",
            role="super_admin",
            is_active=True,
        )
        db.add(existing)
        db.commit()

        result = ensure_demo_user(db, str(tenant.id), email, "new-demo-pw")

        assert result["created"] is False
        assert uuid.UUID(result["user_id"]) == existing.id
        db.expire_all()
        reloaded = db.get(User, existing.id)
        assert reloaded.hashed_password != "old-hash"
        assert reloaded.role == "super_admin"
        assert reloaded.tenant_id == tenant.id
    finally:
        db.close()
