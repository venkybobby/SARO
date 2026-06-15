"""S-1106 / FB-019: is_fixed changes write fixed_by + fixed_at together.

Verifies the audit columns exist and that services.incident_service.set_incident_fixed
is the single write path that stamps (or clears) provenance atomically.
"""
from __future__ import annotations

import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy.types as sa_types
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import sessionmaker

pytestmark = [pytest.mark.regression, pytest.mark.unit]

# SQLite shims for the Postgres-typed columns (same pattern as the suite).
_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base  # noqa: E402
from models import AIIncident  # noqa: E402
from services.incident_service import set_incident_fixed  # noqa: E402

_DB_PATH = Path(tempfile.gettempdir()) / f"saro_pt012_{uuid.uuid4().hex}.db"
_engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _new_incident(db) -> AIIncident:
    inc = AIIncident(title="test incident", category="Privacy & Security", is_fixed=False)
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def test_audit_columns_exist():
    cols = {c.name for c in AIIncident.__table__.columns}
    assert {"fixed_by", "fixed_at"} <= cols


def test_marking_fixed_stamps_actor_and_time():
    db = Session()
    try:
        inc = _new_incident(db)
        assert inc.fixed_by is None and inc.fixed_at is None

        set_incident_fixed(db, inc, fixed=True, actor="auditor@acme.test")

        assert inc.is_fixed is True
        assert inc.fixed_by == "auditor@acme.test"
        assert isinstance(inc.fixed_at, datetime)
    finally:
        db.close()


def test_reopening_clears_attribution():
    db = Session()
    try:
        inc = _new_incident(db)
        set_incident_fixed(db, inc, fixed=True, actor="auditor@acme.test")
        set_incident_fixed(db, inc, fixed=False, actor="auditor@acme.test")

        assert inc.is_fixed is False
        assert inc.fixed_by is None
        assert inc.fixed_at is None
    finally:
        db.close()
