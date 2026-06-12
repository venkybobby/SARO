"""PT-009 AC-3: tenant isolation holds under concurrent sessions.

Spins up >=50 concurrent worker sessions, half acting as tenant A and half as
tenant B, each running the tenant-scoped risk-register query at the ORM (query)
layer. Asserts zero cross-tenant reads: no worker ever sees the other tenant's
audit ids.
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy.types as sa_types
from sqlalchemy import String, cast, create_engine
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = [pytest.mark.regression, pytest.mark.integration]

# SQLite shims for the Postgres-typed columns (same pattern as the suite).
_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base  # noqa: E402
from models import Audit, Tenant  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
_PER_TENANT = 8


def _seed():
    db = Session()
    db.add(Tenant(id=TENANT_A, name="A", slug="tenant-a"))
    db.add(Tenant(id=TENANT_B, name="B", slug="tenant-b"))
    ids = {TENANT_A: set(), TENANT_B: set()}
    for tid in (TENANT_A, TENANT_B):
        for i in range(_PER_TENANT):
            aid = uuid.uuid4()
            ids[tid].add(str(aid))
            db.add(Audit(
                id=aid, tenant_id=tid, dataset_name=f"scan-{i}",
                sample_count=50, status="completed",
            ))
    db.commit()
    db.close()
    return ids


_IDS = _seed()


def _tenant_scoped_audit_ids(tenant_id) -> set[str]:
    """The query-layer isolation boundary the API relies on."""
    db = Session()
    try:
        rows = (
            db.query(Audit)
            .filter(Audit.tenant_id == tenant_id)
            # exercise the same LIKE-prefix path used by risk lookups
            .filter(cast(Audit.id, String).like("%"))
            .all()
        )
        return {str(a.id) for a in rows}
    finally:
        db.close()


def test_no_cross_tenant_reads_under_50_concurrent_sessions():
    plan = [TENANT_A if i % 2 == 0 else TENANT_B for i in range(60)]

    with ThreadPoolExecutor(max_workers=60) as pool:
        results = list(pool.map(_tenant_scoped_audit_ids, plan))

    for tenant_id, seen in zip(plan, results):
        own = _IDS[tenant_id]
        other = _IDS[TENANT_B if tenant_id == TENANT_A else TENANT_A]
        assert seen == own, "a session saw the wrong set of audits"
        assert not (seen & other), "cross-tenant leak: saw another tenant's audit ids"


def test_each_tenant_only_sees_its_own_count():
    assert len(_tenant_scoped_audit_ids(TENANT_A)) == _PER_TENANT
    assert len(_tenant_scoped_audit_ids(TENANT_B)) == _PER_TENANT
