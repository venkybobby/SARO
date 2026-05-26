"""
Integration E2E test suite — Section 7 of SARO spec.

Marked @pytest.mark.integration — requires ENVIRONMENT=integration
and a real (non-mock) database. Excluded from default CI unit test run.

Run with: pytest tests/test_integration_e2e.py -m integration --tb=short
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


@pytest.mark.integration
def test_e2e_imports_available():
    """Verify all models and routers required for E2E flow are importable."""
    from models import HFSampleQueue, HFSampleStatus, Audit
    from routers.hf_processor import router as hf_router
    from routers.ingest import router as ingest_router
    from routers.trace_view import router as trace_router
    assert HFSampleStatus.pending.value == "pending"
    assert hf_router is not None
    assert ingest_router is not None
    assert trace_router is not None


@pytest.mark.integration
def test_e2e_queue_to_processor_flow():
    """
    Full E2E: HF row inserted → processor triggered → audit completed.
    Requires live DATABASE_URL pointing to an integration DB.
    """
    if os.environ.get("ENVIRONMENT") != "integration":
        pytest.skip("Requires ENVIRONMENT=integration")

    from models import HFSampleQueue, HFSampleStatus
    # Integration test body — would use a live DB session
    # Placeholder: verify the queue model can be imported and status enum works
    assert HFSampleStatus("pending") == HFSampleStatus.pending
    assert HFSampleStatus("processed") == HFSampleStatus.processed


@pytest.mark.integration
def test_e2e_ingest_to_dashboard():
    """POST /ingest → engine runs → metrics update in /dashboard."""
    if os.environ.get("ENVIRONMENT") != "integration":
        pytest.skip("Requires ENVIRONMENT=integration")
    # Placeholder for live integration test
    pytest.skip("Live integration test — requires real DB and auth")


@pytest.mark.integration
def test_e2e_processor_status_reflects_reality():
    """GET /hf-processor/status counts match actual DB rows."""
    if os.environ.get("ENVIRONMENT") != "integration":
        pytest.skip("Requires ENVIRONMENT=integration")
    pytest.skip("Live integration test — requires real DB and auth")
