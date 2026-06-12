"""
FND-011: AuditTrace ORM model was missing tenant_id (and declared gate_id
NOT NULL), so the app-path startup migration broke on a fresh Postgres.

Root cause (mirror of FND-006, different table):
  Lifespan order in main.py is create_all_tables() THEN
  apply_pending_migrations(). create_all_tables() builds `audit_traces` from
  the ORM model. Because the model did not declare `tenant_id`, the table was
  created WITHOUT that column; migration 000's
      CREATE INDEX IF NOT EXISTS idx_audit_traces_tenant_id
          ON audit_traces(tenant_id);
  then failed with `column "tenant_id" does not exist`, and the runner
  hard-refuses to serve traffic — so the backend never started on a fresh DB.
  (Pure `psql` application of migrations/*.sql passed, which is why
  STORY-CI-001 AC-3 was green while the app still would not boot.)

  Separately, the model declared `gate_id` NOT NULL, but
  migrations/015_audit_traces_gate_id_nullable.sql relaxes it because the
  post-gate "explain"/"remediate" summary rows legitimately carry gate_id=NULL
  (see scripts/seed_demo.py). The model must reflect the migrated reality.

This test pins (static source checks, mirroring
tests/regression/test_fnd_006_scan_report_tenant_id.py — no live DB required):
  1. AuditTrace declares a tenant_id column.
  2. Every column that migration 000 builds an `idx_audit_traces_*` index on
     is declared on the AuditTrace model (catches the exact create_all-vs-index
     mismatch that broke startup).
  3. AuditTrace.gate_id is declared nullable, matching migration 015.
"""

from __future__ import annotations

import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _audit_trace_body() -> str:
    source = _read(REPO_ROOT / "models.py")
    match = re.search(r"class AuditTrace\(Base\):.*?(?=\nclass )", source, re.DOTALL)
    assert match, "Could not locate class AuditTrace in models.py"
    return match.group(0)


class TestAuditTraceModelHasTenantId:
    def test_model_declares_tenant_id_column(self):
        body = _audit_trace_body()
        assert "tenant_id" in body, (
            "AuditTrace ORM model does not declare a tenant_id column. "
            "create_all_tables() then builds audit_traces without it, and "
            "migration 000's `CREATE INDEX ... ON audit_traces(tenant_id)` "
            "fails at startup on a fresh database (FND-011)."
        )


class TestAuditTraceModelCoversMigrationIndexes:
    def test_every_indexed_audit_trace_column_is_mapped(self):
        """For each `CREATE INDEX ... ON audit_traces(<col>)` in migration 000,
        the AuditTrace model must declare <col> — otherwise create_all_tables()
        builds the table without it and the index DDL fails on startup."""
        m000 = _read(MIGRATIONS_DIR / "000_create_core_tables.sql")
        indexed_cols = set(
            re.findall(
                r"CREATE INDEX[^;]*?ON\s+audit_traces\s*\(\s*([a-z_]+)",
                m000,
                re.IGNORECASE,
            )
        )
        assert indexed_cols, "Expected at least one audit_traces index in migration 000"
        body = _audit_trace_body()
        missing = [c for c in sorted(indexed_cols) if not re.search(rf"\b{c}\b", body)]
        assert not missing, (
            f"AuditTrace model is missing column(s) {missing} that migration 000 "
            f"indexes on audit_traces. create_all_tables() would build the table "
            f"without them and the CREATE INDEX would fail at startup (FND-011)."
        )


class TestAuditTraceGateIdNullable:
    def test_gate_id_declared_nullable(self):
        """migrations/015_audit_traces_gate_id_nullable.sql makes gate_id
        nullable; the ORM model must match so create_all_tables() does not
        re-introduce a NOT NULL the summary rows violate."""
        body = _audit_trace_body()
        gate_line = re.search(
            r"gate_id\s*:\s*Mapped\[[^\]]*\]\s*=\s*mapped_column\([^\n]*", body
        )
        assert gate_line, "Could not find gate_id mapped_column in AuditTrace"
        decl = gate_line.group(0)
        is_nullable = (
            "int | None" in decl or "Optional[int]" in decl or "nullable=True" in decl
        )
        assert is_nullable, (
            "AuditTrace.gate_id is declared NOT NULL but migration 015 makes the "
            "column nullable (post-gate explain/remediate rows carry gate_id=NULL). "
            f"Declaration: {decl!r} (FND-011)."
        )
