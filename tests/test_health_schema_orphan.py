"""Regression: GET /health must not 503 on orphan schema_migrations rows.

Root cause (production incident 2026-06-12 — backend up, DB reachable, every
migration applied, yet /health returned 503 with no error/warning logged):

    schema_ok = schema_version == highest_on_disk

compared the *single highest* row in schema_migrations for exact equality with
the highest *.sql file on disk.  A long-lived production DB carries orphan rows
from migrations that were renamed/removed in a later image; such a row can sort
lexically ABOVE the highest current migration, making max(db) != max(disk)
forever.  That tripped the silent `schema_mismatch` -> 503 branch and blocked
login (every DB-backed endpoint 503s once the machine is marked unhealthy).

The fix: schema is healthy when every migration THIS image ships is applied;
extra/orphan rows are harmless.  These tests pin both directions.

health() calls `next(get_db())` directly (not via Depends), so we patch
database.get_db and main.health_check rather than app.dependency_overrides.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON  # noqa: E402
import sqlalchemy.types as sa_types  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base  # noqa: E402
import models  # noqa: F401,E402  (register all tables, incl. users)

Base.metadata.create_all(engine)

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

MIG_DIR = ROOT / "migrations"
DISK_STEMS = sorted(p.stem for p in MIG_DIR.glob("*.sql"))
# Sorts lexically ABOVE every "NNN_*" stem ('z' > '0') — exactly the orphan
# shape that bricked production.
ORPHAN = "zzz_legacy_removed_migration"


def _fake_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_schema_migrations(versions: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS schema_migrations"))
        conn.execute(text(
            "CREATE TABLE schema_migrations ("
            "version VARCHAR(255) PRIMARY KEY,"
            "checksum VARCHAR(64) NOT NULL DEFAULT 'x',"
            "applied_by VARCHAR(255) NOT NULL DEFAULT 'test')"
        ))
        for v in versions:
            conn.execute(
                text("INSERT INTO schema_migrations(version) VALUES (:v)"),
                {"v": v},
            )


def _get_health() -> tuple[int, dict]:
    healthy = {"ok": True, "error": None, "detail": None}
    # Plain TestClient(app) (no `with`) skips the app lifespan, so startup
    # migrations don't run against SQLite — we only exercise the /health route.
    client = TestClient(app)
    with patch("main.health_check", return_value=healthy), \
         patch("database.get_db", _fake_get_db):
        resp = client.get("/health")
    return resp.status_code, resp.json()


def test_orphan_row_does_not_503_when_all_migrations_applied():
    """The exact production bug: all real migrations applied + a high-sorting
    orphan row -> health must be 200/ok, not a silent schema_mismatch 503."""
    assert DISK_STEMS, "no migration files found on disk"
    assert ORPHAN > DISK_STEMS[-1], "orphan must sort above the highest stem"

    _seed_schema_migrations(DISK_STEMS + [ORPHAN])
    status, body = _get_health()

    assert status == 200, f"orphan row must not 503; body={body}"
    assert body["schema_ok"] is True
    assert body["status"] == "ok"
    assert body["missing_migrations"] == []


def test_genuinely_missing_migration_still_503s():
    """Guard against weakening the gate: if a migration this image ships is
    NOT applied, health must still hard-503 with it listed in missing."""
    absent = DISK_STEMS[-1]
    _seed_schema_migrations(DISK_STEMS[:-1] + [ORPHAN])  # everything but `absent`
    status, body = _get_health()

    assert status == 503, f"missing migration must 503; body={body}"
    assert body["schema_ok"] is False
    assert body["status"] == "schema_mismatch"
    assert absent in body["missing_migrations"]
