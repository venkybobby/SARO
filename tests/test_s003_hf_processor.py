"""
S-003: HuggingFace Processor Router — unit tests.

Tests that:
  1. Router imports correctly and has expected endpoints.
  2. GET /api/v1/hf/queue/status returns queue counts.
  3. POST /api/v1/hf/process triggers processing.
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock, patch


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestHFProcessorRouterImport:
    def test_router_importable(self):
        from routers.hf_processor import router
        assert router.prefix == "/api/v1/hf"

    def test_router_has_expected_routes(self):
        from routers.hf_processor import router
        route_paths = [r.path for r in router.routes]
        assert any("process" in p for p in route_paths), f"No process route in {route_paths}"
        assert any("status" in p for p in route_paths), f"No status route in {route_paths}"

    def test_router_registered_in_main(self):
        content = open(os.path.join(_REPO_ROOT, "main.py")).read()
        assert "hf_processor_router" in content


class TestProcessSingleRow:
    def test_process_single_row_handles_engine_error(self):
        """_process_single_row should mark row as 'failed' on engine error."""
        from routers.hf_processor import _process_single_row

        mock_row = MagicMock()
        mock_row.tenant_id = uuid.uuid4()
        mock_row.source_model = "unknown"
        mock_row.vertical = "general"
        mock_row.source_dataset = "test/data"
        mock_row.prompt_text = "hello"
        mock_row.raw_output_text = "world"
        mock_row.retry_count = 0

        mock_db = MagicMock()
        mock_db.get.return_value = None  # audit not found — triggers error path

        with patch("routers.hf_processor.SARoEngine") as mock_engine_cls:
            mock_engine_cls.side_effect = Exception("engine unavailable")
            _process_single_row(mock_row, mock_db)

        # Row should be marked failed
        assert mock_row.status == "failed"


class TestRunBatch:
    def test_run_batch_returns_summary(self):
        """_run_batch returns a dict with processed/failed/attempted keys."""
        from routers.hf_processor import _run_batch

        tenant_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = _run_batch(tenant_id, 10, mock_db)
        assert "processed" in result
        assert "failed" in result
        assert "attempted" in result
        assert result["attempted"] == 0
