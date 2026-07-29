"""FND-093 — users.role had no DB-level CHECK constraint / enum.

`models.User.role` is a plain `String(50)` (default `"operator"`) with only a
code comment ("Roles: super_admin | operator") documenting the two valid
values -- nothing at the schema level stops an arbitrary or typo'd string
(e.g. `"supper_admin"`) from being persisted. Every current write site
(signup, seed scripts, SSO provisioning) happens to hardcode one of the two
literals, so this has never been forced open by an incident, but it is a
silent hole: `auth.require_role(...)` compares `current_user.role` against
string literals, so a corrupted row fails *safe* (access denied) with zero
schema-level signal that the account itself is broken -- and every future
role-management write path inherits the same gap.

Fix: `CheckConstraint("role IN ('super_admin', 'operator')", name="ck_users_role_valid")`
on `models.User.__table_args__`, applied to existing databases by
`migrations/044_users_role_check.sql`. Defense-in-depth only -- no code path
writes an arbitrary role today (verified: the only other role-shaped literals
in the tree, e.g. `"viewer"`/`"admin"`/`"demo_viewer"`, appear exclusively in
`MagicMock(spec=User)` / `SimpleNamespace` test doubles that never reach the
database).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
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


def _make_tenant(db) -> Tenant:
    slug = f"co-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(id=uuid.uuid4(), name=slug, slug=slug)
    db.add(tenant)
    db.flush()
    return tenant


@pytest.mark.regression
def test_invalid_role_rejected_at_db_level():
    db = _Session()
    try:
        tenant = _make_tenant(db)
        bad = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=f"typo-{uuid.uuid4().hex[:8]}@test.example",
            hashed_password="x",
            role="supper_admin",  # typo — must never persist silently
            is_active=True,
        )
        db.add(bad)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


@pytest.mark.regression
@pytest.mark.parametrize("valid_role", ["super_admin", "operator"])
def test_valid_roles_still_accepted(valid_role):
    db = _Session()
    try:
        tenant = _make_tenant(db)
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=f"ok-{uuid.uuid4().hex[:8]}@test.example",
            hashed_password="x",
            role=valid_role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.expire_all()
        assert db.get(User, user.id).role == valid_role
    finally:
        db.close()
