"""
S-201: Dashboard Ingest Tab — tests for Streamlit frontend.

The SARO frontend is Streamlit-based (frontend/tabs/).
Tests verify the ingest tab module exists with required functions.
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestIngestTabFile:
    def test_ingest_tab_file_exists(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        assert os.path.exists(tab_path), "frontend/tabs/ingest.py not found"

    def test_source_models_defined(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "_SOURCE_MODELS" in content
        assert "claude" in content
        assert "openai" in content

    def test_verticals_defined(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "_VERTICALS" in content
        assert "healthcare" in content
        assert "finance" in content

    def test_render_function_defined(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "def render(" in content

    def test_ingest_endpoint_referenced(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "/api/v1/ingest" in content

    def test_status_polling_referenced(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "/api/v1/audits/" in content

    def test_sdk_snippet_referenced(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "/api/v1/sdk/snippet" in content

    def test_risk_color_helper_defined(self):
        tab_path = os.path.join(_REPO_ROOT, "frontend", "tabs", "ingest.py")
        content = open(tab_path).read()
        assert "_get_risk_color" in content


class TestComplianceMatrixCoverage:
    def test_compliance_matrix_router_importable(self):
        from routers.compliance_matrix import router
        assert router is not None

    def test_coverage_endpoint_exists(self):
        from routers.compliance_matrix import router
        paths = [r.path for r in router.routes]
        assert any("coverage" in p for p in paths), (
            f"No coverage endpoint in compliance_matrix router: {paths}"
        )

    def test_hf_processor_status_router_importable(self):
        from routers.hf_processor import router
        paths = [r.path for r in router.routes]
        assert any("status" in p for p in paths)
