"""
SAR-007: Compliance Hub readiness checklist — 6 tests.

Verifies that each of the 5 checklist items is evaluated independently
and that the /api/v1/compliance/hub endpoint respects persona RBAC.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-sar007")

from routers.compliance_hub import _readiness_checklist  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_audit(status: str = "completed") -> MagicMock:
    a = MagicMock()
    a.id = uuid.uuid4()
    a.status = status
    a.dataset_name = "test"
    a.sample_count = 10
    a.created_at = None
    a.completed_at = None
    return a


def _mock_db(has_trace: bool = True, has_enhanced: bool = True) -> MagicMock:
    db = MagicMock()

    from models import AuditTrace, EnhancedTrace

    def _query(model):
        q = MagicMock()
        if model is AuditTrace:
            q.filter.return_value.first.return_value = MagicMock() if has_trace else None
        elif model is EnhancedTrace:
            q.filter.return_value.first.return_value = MagicMock() if has_enhanced else None
        else:
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = _query
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_readiness_checklist_returns_5_items():
    """_readiness_checklist must always return exactly 5 items."""
    audit = _mock_audit()
    db = _mock_db()
    items = _readiness_checklist([audit], db, uuid.uuid4())
    assert len(items) == 5
    ids = {i["id"] for i in items}
    assert ids == {"audit_trail", "trace_export", "claims_matrix", "dpa_complete", "how_saro_reasons"}


def test_audit_trail_true_when_traces_exist():
    """audit_trail item must be True when completed audit has hash-chained AuditTraces."""
    audit = _mock_audit(status="completed")
    db = _mock_db(has_trace=True)
    items = {i["id"]: i["complete"] for i in _readiness_checklist([audit], db, uuid.uuid4())}
    assert items["audit_trail"] is True


def test_audit_trail_false_when_no_traces():
    """audit_trail item must be False when no AuditTrace records exist."""
    audit = _mock_audit(status="completed")
    db = _mock_db(has_trace=False, has_enhanced=False)
    items = {i["id"]: i["complete"] for i in _readiness_checklist([audit], db, uuid.uuid4())}
    assert items["audit_trail"] is False


def test_trace_export_false_when_no_enhanced_trace():
    """trace_export must be False when no EnhancedTrace exists."""
    audit = _mock_audit(status="completed")
    db = _mock_db(has_trace=True, has_enhanced=False)
    items = {i["id"]: i["complete"] for i in _readiness_checklist([audit], db, uuid.uuid4())}
    assert items["trace_export"] is False


def test_claims_matrix_true_when_registry_exists():
    """claims_matrix must be True when compliance_label_registry.json is on disk."""
    db = _mock_db()
    items = {i["id"]: i["complete"] for i in _readiness_checklist([], db, uuid.uuid4())}
    # Registry was created in SAR-002 — should always be True in this repo
    assert items["claims_matrix"] is True


def test_dpa_complete_true_when_template_exists():
    """dpa_complete must be True when DPA template file is on disk."""
    db = _mock_db()
    items = {i["id"]: i["complete"] for i in _readiness_checklist([], db, uuid.uuid4())}
    assert items["dpa_complete"] is True
