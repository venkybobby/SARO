"""Test-only SQLite dialect shim for `SELECT ... FOR UPDATE` (Postgres-only syntax).

`routers.scan._persist_traces` row-locks the parent Audit with `FOR UPDATE`
(intentional, for concurrent-write serialization against the real Postgres
database). SQLite has no such clause. This is the same category of gap
`conftest.py` already shims for PG_UUID/PG_JSON — a dialect incompatibility in
test tooling, not a change to production behavior (production always runs
against Postgres, where the row lock is real and necessary).

Used by tests that exercise the CLI's real ingest submit path (`_default_submit`
-> `submit_audit_sync` -> `_persist_traces`) against an in-memory SQLite DB.
"""

from __future__ import annotations

from sqlalchemy import text as _sql_text
from sqlalchemy.orm import Session


def install(monkeypatch) -> None:
    orig_execute = Session.execute

    def _sqlite_safe_execute(self, statement, *args, **kwargs):
        stmt_str = str(statement)
        if "FOR UPDATE" in stmt_str:
            statement = _sql_text(stmt_str.replace(" FOR UPDATE", ""))
        return orig_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", _sqlite_safe_execute)
