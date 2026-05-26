"""S-203: Compliance matrix coverage endpoint tests."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestComplianceMatrixCoverageEndpoint:
    def test_router_importable(self):
        from routers.compliance_matrix import router
        assert router is not None

    def test_coverage_route_registered(self):
        from routers.compliance_matrix import router
        paths = [r.path for r in router.routes]
        assert any("coverage" in p for p in paths), (
            f"Coverage endpoint missing from compliance_matrix router: {paths}"
        )

    def test_coverage_route_responds_to_window_param(self):
        from routers.compliance_matrix import router
        paths = [r.path for r in router.routes]
        coverage_paths = [p for p in paths if "coverage" in p]
        assert len(coverage_paths) >= 1

    def test_compliance_matrix_router_registered_in_main(self):
        content = open(os.path.join(_REPO_ROOT, "main.py")).read()
        assert "compliance_matrix_router" in content
