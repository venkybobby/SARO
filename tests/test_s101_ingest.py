"""S-101: POST /api/v1/ingest endpoint — unit tests."""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestIngestSchemas:
    def test_ingest_request_schema_importable(self):
        from routers.ingest import IngestRequest, IngestResponse
        assert IngestRequest is not None
        assert IngestResponse is not None

    def test_ingest_request_valid_source_models(self):
        from routers.ingest import IngestRequest
        import pydantic
        fields = IngestRequest.model_fields
        assert "source_model" in fields
        assert "prompt" in fields
        assert "raw_output" in fields
        assert "vertical" in fields
        assert "tenant_id" in fields

    def test_ingest_response_has_required_fields(self):
        from routers.ingest import IngestResponse
        fields = IngestResponse.model_fields
        assert "audit_id" in fields
        assert "status" in fields
        assert "trace_url" in fields


class TestIngestRouter:
    def test_router_importable(self):
        from routers.ingest import router
        assert router.prefix == "/api/v1"

    def test_ingest_route_exists(self):
        from routers.ingest import router
        paths = [r.path for r in router.routes]
        assert any("ingest" in p for p in paths), f"No ingest route in {paths}"

    def test_router_registered_in_main(self):
        content = open(os.path.join(_REPO_ROOT, "main.py")).read()
        assert "ingest_router" in content

    def test_migration_008_exists(self):
        migration_path = os.path.join(_REPO_ROOT, "migrations", "008_audit_text_fields.sql")
        assert os.path.exists(migration_path), "Migration 008 not found"

    def test_migration_008_has_prompt_text(self):
        migration_path = os.path.join(_REPO_ROOT, "migrations", "008_audit_text_fields.sql")
        content = open(migration_path).read()
        assert "prompt_text" in content
        assert "raw_output_text" in content
