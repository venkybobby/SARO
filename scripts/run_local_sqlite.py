#!/usr/bin/env python3
"""SQLite-backed local SARO backend — demo/persona verification without Docker.

`scripts/run_local.ps1` is the full local recipe (dedicated Postgres container).
This launcher is the no-Docker fallback the persona UI walk needs: it applies
the SAME shims the test suite uses (conftest.py — Postgres UUID/JSON column
types on SQLite, engine override) plus no-ops for the Postgres-flavored startup
migrations, then seeds the demo corpus and serves ``main:app``.

    python scripts/run_local_sqlite.py --seed          # first run: seed + serve
    python scripts/run_local_sqlite.py                 # subsequent runs: serve

State lives in ``.local-sqlite-demo.db`` at the repo root (gitignored class of
artifact — delete it to reset). Local demo verification ONLY: SQLite has no
RLS, so tenant isolation relies on app-layer filters alone here — never ship
or benchmark against this configuration.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / ".local-sqlite-demo.db"


def _bootstrap() -> None:
    """Shim Postgres-only pieces, then point database.py at file-backed SQLite.

    Order matters (mirrors conftest.py): column-type shims BEFORE models import,
    engine/session overrides BEFORE main import so main's ``from database
    import ...`` names bind to the patched callables.
    """
    os.environ.setdefault("SARO_ENV", "test")
    os.environ.setdefault("JWT_SECRET_KEY", "local-sqlite-demo-secret")
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{DB_PATH}")

    import sqlalchemy.types as sa_types
    from sqlalchemy.dialects.postgresql import JSON as PG_JSON
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    _orig_uuid_init = PG_UUID.__init__

    def _sqlite_uuid_init(self, *args, **kwargs):
        kwargs.pop("as_uuid", None)
        _orig_uuid_init(self, *args, **kwargs)

    PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
    PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
    PG_JSON.none_as_null = False

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database

    eng = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=eng)
    database._get_engine = lambda: eng  # type: ignore[assignment]
    database._get_session_factory = lambda: factory  # type: ignore[assignment]

    # Startup migrations are Postgres SQL; on SQLite the schema comes from
    # create_all_tables() instead (exactly what conftest does).
    database.apply_pending_migrations = lambda applied_by="system": []  # type: ignore[assignment]
    database.ensure_app_schema = lambda: None  # type: ignore[assignment]
    database.verify_migration_objects = lambda: None  # type: ignore[assignment]

    import models  # noqa: F401 — register every table on Base.metadata

    database.Base.metadata.create_all(eng)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seed", action="store_true", help="seed demo corpus + users first"
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-serve", action="store_true", help="bootstrap/seed only, then exit"
    )
    args = parser.parse_args()

    _bootstrap()

    if args.seed:
        from scripts import seed_demo

        seed_demo.seed()
        from scripts.demo_persona_ui_verification import ensure_user

        rc = ensure_user()
        if rc != 0:
            return rc

    if args.no_serve:
        print(f"bootstrap complete — db at {DB_PATH}")
        return 0

    import uvicorn

    import main as app_main

    uvicorn.run(app_main.app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
