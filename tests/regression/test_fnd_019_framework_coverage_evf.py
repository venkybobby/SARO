"""FND-019: board summary emitted hardcoded framework-coverage percentages.

``get_board_summary`` returned ``{"EU AI Act": 72.0, "NIST AI RMF": 68.0, ...}`` —
invented numbers — and rendered them into the board PDF as "Coverage %". Per
docs/COMPLIANCE_CLAIMS_MATRIX.md (SARO-RISK-001, EVF Tier-3) no framework claim
has completed External SME Validation, so *no* coverage percentage may be
published in external materials.

Fix: framework_coverage now maps each framework to its EVF validation-status
string, never a numeric percentage; the PDF renders status, not "%".
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from routers.risk_dashboard import get_board_summary

pytestmark = pytest.mark.regression


def _board_user():
    u = MagicMock()
    u.tenant_id = uuid.uuid4()
    u.role = "super_admin"
    u.persona_role = "risk_officer"
    return u


def _db_with_one_audit():
    db = MagicMock()
    audit = MagicMock()
    audit.id = uuid.uuid4()
    audit.created_at = datetime.utcnow()
    report = MagicMock()
    report.overall_risk_score = 0.85
    db.query.return_value.join.return_value.filter.return_value.all.return_value = [
        (audit, report)
    ]
    db.query.return_value.filter.return_value.all.return_value = []
    return db


def test_framework_coverage_has_no_numeric_percentages():
    result = get_board_summary(db=_db_with_one_audit(), current_user=_board_user())
    fc = result["framework_coverage"]
    assert fc, "framework_coverage should still list the in-scope frameworks"
    for framework, value in fc.items():
        assert not isinstance(value, (int, float)), (
            f"{framework} still publishes a numeric coverage value ({value!r}) — "
            "EVF Tier-3 forbids this (FND-019)"
        )
        assert "Not for External Claim" in str(value), (
            f"{framework} must carry the EVF Tier-3 status, got {value!r}"
        )


def test_source_no_longer_hardcodes_fake_coverage_percentages():
    src = pathlib.Path(
        pathlib.Path(__file__).parents[2] / "routers" / "risk_dashboard.py"
    ).read_text(encoding="utf-8")
    for fake in ("72.0", "68.0", "55.0", "48.0"):
        assert fake not in src, (
            f"Hardcoded fake coverage percentage {fake} still present (FND-019)"
        )
