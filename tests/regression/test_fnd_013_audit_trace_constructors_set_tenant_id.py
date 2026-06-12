"""
FND-013: every AuditTrace(...) construction site must set tenant_id.

FND-011 added the audit_traces.tenant_id column, but the insert sites still
created rows without it, so new traces were written with tenant_id IS NULL —
the same failure mode FND-006 fixed for ScanReport, one table over. Under
tenant_isolation_audit_traces (migrations/001, `tenant_id::text =
current_setting('app.current_tenant', true)`), a NULL-tenant row matches no
tenant. It is fail-closed (no cross-tenant leak — the trace read path also
scopes by the parent audit's tenant), but it negates the defense-in-depth
column the moment RLS is activated per-request.

Fix: source tenant_id from the parent audit at each AuditTrace(...) site
(routers/scan.py reads it from the locked parent audit row; scripts/seed_demo.py
uses audit_obj.tenant_id).

This pins (static source check, mirroring
tests/regression/test_fnd_006_scan_report_tenant_id.py::TestScanReportConstructorsSetTenantId):
every AuditTrace(...) construction block in application code sets tenant_id=.
"""

from __future__ import annotations

import pathlib
import re

import pytest


REPO_ROOT = pathlib.Path(__file__).parents[2]


def _read(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text(encoding="utf-8")


class TestAuditTraceConstructorsSetTenantId:
    @pytest.mark.parametrize(
        "relpath",
        [
            "routers/scan.py",
            "scripts/seed_demo.py",
        ],
    )
    def test_audit_trace_construction_sets_tenant_id(self, relpath):
        source = _read(relpath)

        # Find each `AuditTrace(` ... matching `)` block (non-nested) and assert
        # tenant_id= is set, so the row is never written with NULL tenant_id.
        for match in re.finditer(r"AuditTrace\(", source):
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
                f"{relpath}: an AuditTrace(...) construction does not set "
                f"tenant_id=, so the row is created with NULL tenant_id and "
                f"becomes invisible under tenant_isolation_audit_traces RLS "
                f"(FND-013):\n{block}"
            )
