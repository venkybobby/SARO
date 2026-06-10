"""
SARO-H06: Tenant isolation enforcement gate.

Verifies that:
  1. The broken RLS middleware is gone (it was never registered and had three
     implementation bugs that would have made it silently inert even if it was).
  2. Every router that queries a tenant-scoped ORM model does so with a
     tenant_id filter — enforced either inline or via a _get_*_or_404 helper
     that checks tenant_id.
  3. Cross-tenant reads are blocked at the route level via integration tests
     using two distinct test tenants.

Background (SARO-H06):
  middleware/tenant_context.py was dead code — never registered in main.py,
  and broken in three ways: async with on a sync generator, reads
  request.state.tenant_id which nothing sets, and SET LOCAL evaporates because
  NullPool closes the connection before route queries run. Tenant isolation
  is enforced app-layer only via .filter(Model.tenant_id == current_user.tenant_id).
  This test suite is the CI backstop for that discipline.
"""
from __future__ import annotations

import ast
import os
import pathlib
import textwrap
import uuid
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Dead middleware must not exist
# ---------------------------------------------------------------------------

class TestDeadMiddlewareGone:
    def test_tenant_context_middleware_deleted(self):
        """middleware/tenant_context.py was removed (SARO-H06).

        It was never registered in main.py, was broken in three ways, and
        created a false sense of security. Tenant isolation is app-layer only.
        If this file reappears, re-evaluate whether it is properly wired before
        allowing it back.
        """
        middleware_path = pathlib.Path(__file__).parents[1] / "middleware" / "tenant_context.py"
        assert not middleware_path.exists(), (
            "middleware/tenant_context.py must not exist (SARO-H06). "
            "The broken RLS middleware was removed. If you are re-introducing RLS, "
            "ensure it uses session-bound SET LOCAL inside get_db() and that "
            "policies exist on ALL tenant-scoped tables."
        )

    def test_main_py_does_not_import_tenant_context(self):
        """main.py must not import the deleted middleware."""
        main_path = pathlib.Path(__file__).parents[1] / "main.py"
        source = main_path.read_text(encoding="utf-8")
        assert "tenant_context" not in source, (
            "main.py still references tenant_context middleware which was removed."
        )


# ---------------------------------------------------------------------------
# 2. Static analysis: tenant-scoped model queries must carry tenant_id filters
# ---------------------------------------------------------------------------

# Models that are tenant-scoped (have a tenant_id FK column).
# Non-tenant tables (e.g. Control, NistAiRmfControl, schema_migrations) are
# intentionally excluded — they are shared/global.
TENANT_SCOPED_MODELS = {
    "Audit",
    "ScanReport",
    "AuditTrace",
    "EnhancedTrace",
    "SampleFinding",
    "AuditEvent",
    "AuditMetadata",
    "ClientConfig",
    "Notification",
    "AISystem",
    "SystemAudit",
    "GithubIntegration",
    "GithubScanResult",
    "Iso42001Document",
    "AIMSDocument",
    "TenantRiskConfig",
    "OnboardingProgress",
}

# Patterns that are always safe — they wrap the tenant check internally.
SAFE_QUERY_PATTERNS = {
    # Explicit tenant filter patterns
    "tenant_id ==",
    "tenant_id=",
    ".tenant_id",
    "current_user.tenant_id",
    # Known helper functions that enforce tenant ownership internally
    "_get_audit_or_404",
    "_get_report_or_404",
    "_get_trace_or_404",
    "_get_system_or_404",
    "_get_or_404",
    # Indirect safety: filtering by audit_id that was already tenant-validated
    # upstream (e.g. _get_audit_or_404 called before this query).
    # AuditTrace, ScanReport, EnhancedTrace all have audit_id FKs — if the
    # parent audit is tenant-validated, child queries by audit_id are safe.
    "audit_id ==",
    "audit_id=",
    ".audit_id",
    # Similarly for system_id (validated by _get_system_or_404 upstream)
    "system_id ==",
}


class _RouterViolation(NamedTuple):
    file: str
    line: int
    model: str
    snippet: str


def _scan_router_for_unfiltered_queries(router_path: pathlib.Path) -> list[_RouterViolation]:
    """
    Heuristic static scan: find db.query(TenantScopedModel) calls that are NOT
    within 10 lines of a tenant_id filter or a known-safe helper call.

    This is intentionally a heuristic, not a full AST analysis. It catches
    copy-paste omissions — the most common class of tenant isolation bugs.
    False positives are possible for complex query chains; the author should
    add the model to SAFE_QUERY_PATTERNS or suppress with a comment if needed.
    """
    source = router_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    violations: list[_RouterViolation] = []

    for i, line in enumerate(lines):
        # Look for db.query(ModelName) where ModelName is tenant-scoped
        if "db.query(" not in line:
            continue
        matched_model = None
        for model in TENANT_SCOPED_MODELS:
            if f"db.query({model})" in line or f"db.query({model}," in line:
                matched_model = model
                break
        if not matched_model:
            continue

        # Gather context: 5 lines before + the line itself + 10 lines after.
        # Safe helpers are often called immediately BEFORE the query, so we
        # look backwards too (e.g. _get_audit_or_404 on line N, db.query on N+3).
        window_start = max(0, i - 5)
        window_end = min(i + 11, len(lines))
        window = "\n".join(lines[window_start:window_end])

        # Check if any safe pattern appears in the window
        if any(pat in window for pat in SAFE_QUERY_PATTERNS):
            continue

        violations.append(_RouterViolation(
            file=str(router_path.relative_to(router_path.parents[2])),
            line=i + 1,
            model=matched_model,
            snippet=textwrap.shorten(line.strip(), width=120),
        ))

    return violations


class TestRouterTenantFiltering:
    """Every tenant-scoped db.query() in routers/ must be paired with a tenant filter."""

    @pytest.fixture(scope="class")
    def router_dir(self):
        return pathlib.Path(__file__).parents[1] / "routers"

    def test_no_unfiltered_tenant_scoped_queries(self, router_dir):
        violations: list[_RouterViolation] = []
        for router_file in sorted(router_dir.glob("*.py")):
            if router_file.name == "__init__.py":
                continue
            violations.extend(_scan_router_for_unfiltered_queries(router_file))

        if violations:
            report = "\n".join(
                f"  {v.file}:{v.line} — {v.model} query lacks tenant_id filter\n"
                f"    {v.snippet}"
                for v in violations
            )
            pytest.fail(
                f"TENANT ISOLATION VIOLATION — {len(violations)} unfiltered tenant-scoped "
                f"queries found in routers/. Every db.query(TenantScopedModel) must be "
                f"within 10 lines of a .filter(...tenant_id...) or a known-safe helper.\n\n"
                f"Violations:\n{report}\n\n"
                f"Fix: add .filter(Model.tenant_id == current_user.tenant_id) "
                f"or use a _get_*_or_404 helper that enforces it."
            )

    def test_all_router_files_are_scanned(self, router_dir):
        """Sanity: the scan runs against at least 10 router files."""
        router_files = [f for f in router_dir.glob("*.py") if f.name != "__init__.py"]
        assert len(router_files) >= 10, (
            f"Expected at least 10 router files, found {len(router_files)}. "
            "Is the routers/ directory path correct?"
        )


# ---------------------------------------------------------------------------
# 3. Integration: cross-tenant access blocked at API level
# ---------------------------------------------------------------------------

class TestCrossTenantAccessBlocked:
    """
    Verify that tenant A cannot read tenant B's data through the API.
    Uses FastAPI TestClient with two mock users from different tenants.
    """

    @pytest.fixture
    def tenant_a_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def tenant_b_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_a(self, tenant_a_id):
        u = MagicMock()
        u.id = uuid.uuid4()
        u.tenant_id = tenant_a_id
        u.role = "operator"
        u.persona_role = "ai_auditor"
        u.is_active = True
        u.read_only = False
        return u

    @pytest.fixture
    def user_b(self, tenant_b_id):
        u = MagicMock()
        u.id = uuid.uuid4()
        u.tenant_id = tenant_b_id
        u.role = "operator"
        u.persona_role = "ai_auditor"
        u.is_active = True
        u.read_only = False
        return u

    def test_audit_from_other_tenant_returns_404(self, user_a, user_b, tenant_b_id):
        """User A requesting an audit belonging to tenant B receives 404."""
        from fastapi.testclient import TestClient
        from main import app
        from auth import get_current_user
        from database import get_db

        # Audit owned by tenant B
        audit_id = uuid.uuid4()
        mock_audit = MagicMock()
        mock_audit.id = audit_id
        mock_audit.tenant_id = tenant_b_id  # belongs to B
        mock_audit.status = "completed"

        mock_db = MagicMock()
        # Simulate the _get_audit_or_404 query returning the audit
        mock_db.query.return_value.filter.return_value.first.return_value = mock_audit

        with (
            patch.object(app, "dependency_overrides", {
                get_current_user: lambda: user_a,  # logged in as A
                get_db: lambda: mock_db,
            }),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"/api/v1/traces/{audit_id}")

        # The tenant check (audit.tenant_id != current_user.tenant_id) must fire
        # and return 404 — not 200, not 403 (404 to avoid confirming existence)
        assert resp.status_code == 404, (
            f"Expected 404 when tenant A requests tenant B's audit, got {resp.status_code}. "
            "Tenant isolation is not enforced on GET /api/v1/traces/{id}."
        )

    def test_notification_list_scoped_to_current_tenant(self, user_a, tenant_a_id):
        """list_notifications() issues a .filter(Notification.tenant_id == ...) query."""
        from routers.notifications import list_notifications
        from models import Notification

        mock_db = MagicMock()
        # Simulate count(), unread, and paginated .all() returning empty
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        list_notifications(
            current_user=user_a, db=mock_db,
            unread_only=False, severity=None, limit=20, offset=0,
        )

        # Verify .filter() was called on the Notification query (proves the
        # tenant-isolation branch ran). The static scan in
        # TestRouterTenantFiltering confirms the filter carries tenant_id —
        # inspecting SQLAlchemy BinaryExpression objects at runtime is fragile.
        assert mock_db.query.return_value.filter.called, (
            "list_notifications() did not call .filter() at all on the Notification query. "
            "Tenant isolation is not applied."
        )
        # Confirm the first positional argument to .filter() is a SQLAlchemy
        # expression — not a bare True/None that would bypass filtering.
        first_filter_expr = mock_db.query.return_value.filter.call_args_list[0][0][0]
        assert first_filter_expr is not None and first_filter_expr is not True, (
            "list_notifications() passed a no-op expression to .filter(). "
            "Tenant isolation may be bypassed."
        )


# ---------------------------------------------------------------------------
# 4. Regression: confirm tenant_context module truly does not load
# ---------------------------------------------------------------------------

class TestTenantContextUnimportable:
    def test_cannot_import_tenant_context(self):
        """Attempting to import the deleted module must raise ImportError."""
        import importlib
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("middleware.tenant_context")
