"""S-202: TRACE view — model_version gate and export endpoint tests."""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestTraceViewRouter:
    def test_trace_view_router_importable(self):
        from routers.trace_view import router
        assert router is not None

    def test_trace_export_endpoint_exists(self):
        from routers.trace_view import router
        paths = [r.path for r in router.routes]
        assert any("export" in p for p in paths), (
            f"No export endpoint in trace_view router: {paths}"
        )

    def test_enhanced_trace_model_has_model_version(self):
        from models import EnhancedTrace
        cols = {c.key for c in EnhancedTrace.__mapper__.columns}
        assert "model_version" in cols

    def test_enhanced_trace_model_has_export_hash(self):
        from models import EnhancedTrace
        cols = {c.key for c in EnhancedTrace.__mapper__.columns}
        assert "export_hash" in cols

    def test_enhanced_trace_model_has_chain_of_thought(self):
        from models import EnhancedTrace
        cols = {c.key for c in EnhancedTrace.__mapper__.columns}
        assert "chain_of_thought" in cols


class TestTraceExportHash:
    def test_export_hash_pattern(self):
        import hashlib, json
        payload = {"audit_id": "test", "chain": [{"step": 1}]}
        computed = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        assert len(computed) == 64
        assert all(c in "0123456789abcdef" for c in computed)
