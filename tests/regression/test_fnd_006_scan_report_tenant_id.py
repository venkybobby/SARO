"""
FND-006: scan_reports.tenant_id was added (nullable) by
migrations/002_add_tenant_id_columns.sql but never backfilled, and
application code never set it on insert.

Under the tenant_isolation_scan_reports RLS policy
(USING (tenant_id::text = current_setting('app.current_tenant', true))),
NULL = x evaluates to NULL (not true) in Postgres — so any scan_reports row
with tenant_id IS NULL is invisible to every tenant. Fail-closed, but broken.

This test pins two things:
  1. A migration backfills scan_reports.tenant_id from the parent audits row
     for any pre-existing rows (mirrors the audit_traces backfill in
     migrations/002_add_tenant_id_columns.sql).
  2. Every ScanReport(...) construction site sets tenant_id, so new rows are
     never created with NULL tenant_id.
"""
from __future__ import annotations

import pathlib
import re

import pytest


REPO_ROOT = pathlib.Path(__file__).parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


class TestScanReportsTenantIdBackfilled:
    def test_a_migration_backfills_scan_reports_tenant_id(self):
        """
        At least one migration must UPDATE scan_reports.tenant_id from the
        parent audits row, guarded by `WHERE ... tenant_id IS NULL` (the same
        pattern used for audit_traces in migrations/002_add_tenant_id_columns.sql).
        """
        sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        assert sql_files, f"No migration files found under {MIGRATIONS_DIR}"

        backfill_pattern = re.compile(
            r"UPDATE\s+scan_reports\b.*?SET\s+tenant_id\s*=.*?audits.*?WHERE\s+.*tenant_id\s+IS\s+NULL",
            re.IGNORECASE | re.DOTALL,
        )

        matches = [
            f for f in sql_files if backfill_pattern.search(_read(f))
        ]

        assert matches, (
            "No migration backfills scan_reports.tenant_id from audits "
            "(UPDATE scan_reports ... SET tenant_id = (... audits ...) "
            "WHERE tenant_id IS NULL). Without this, pre-existing "
            "scan_reports rows have NULL tenant_id and are invisible under "
            "the tenant_isolation_scan_reports RLS policy to every tenant "
            "(NULL = x is NULL, not true)."
        )


class TestScanReportConstructorsSetTenantId:
    """
    Every ScanReport(...) construction site in application code must pass
    tenant_id=... so newly-created rows are never NULL.
    """

    @pytest.mark.parametrize(
        "relpath",
        [
            "routers/scan.py",
            "routers/ingest.py",
            "routers/hf_processor.py",
            "routers/output_audit.py",
            "scripts/seed_demo.py",
        ],
    )
    def test_scan_report_construction_sets_tenant_id(self, relpath):
        source = _read(REPO_ROOT / relpath)

        # Find each `ScanReport(` ... matching `)` block (non-nested — good
        # enough since none of these constructors nest parens around the
        # whole call).
        for match in re.finditer(r"ScanReport\(", source):
            start = match.end()
            depth = 1
            end = start
            while depth > 0:
                ch = source[end]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                end += 1
            block = source[start:end]
            assert "tenant_id=" in block, (
                f"{relpath}: a ScanReport(...) construction does not set "
                f"tenant_id=, so the row will be created with NULL "
                f"tenant_id and become invisible under RLS:\n{block}"
            )


class TestScanReportModelHasTenantId:
    def test_model_declares_tenant_id_column(self):
        source = _read(REPO_ROOT / "models.py")
        scan_report_match = re.search(
            r"class ScanReport\(Base\):.*?(?=\nclass )", source, re.DOTALL
        )
        assert scan_report_match, "Could not locate class ScanReport in models.py"
        body = scan_report_match.group(0)
        assert "tenant_id" in body, (
            "ScanReport ORM model does not declare a tenant_id column — "
            "the scan_reports.tenant_id DB column (added in "
            "migrations/002_add_tenant_id_columns.sql) is unmapped."
        )
