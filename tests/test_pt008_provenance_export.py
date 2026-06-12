"""PT-008: engine version + rule-pack hash are part of the signed export payload.

The export_hash must change if either provenance field changes, so a tampered or
mismatched engine/rule-pack cannot ride inside an otherwise-valid signed report.
Reports created before provenance was recorded sign an explicit sentinel.
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from routers.trace_export import _PROVENANCE_UNAVAILABLE, _build_signed_json

pytestmark = pytest.mark.unit


def _audit():
    return SimpleNamespace(
        id=uuid.uuid4(),
        dataset_name="ds",
        completed_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )


def _enhanced():
    return SimpleNamespace(executive_summary="summary")


def _report(engine_version="8.0.0", rule_pack_hash="a" * 64, matrix="2026-06-02"):
    return SimpleNamespace(
        confidence_score=0.7,
        overall_risk_score=42.0,
        mit_coverage_score=0.5,
        engine_version=engine_version,
        rule_pack_hash=rule_pack_hash,
        compliance_matrix_version=matrix,
    )


def test_export_hash_covers_engine_version():
    rj1, h1, _ = _build_signed_json(_audit(), _enhanced(), [], _report(engine_version="8.0.0"))
    rj2, h2, _ = _build_signed_json(_audit(), _enhanced(), [], _report(engine_version="8.0.1"))
    assert rj1["audit_id"] != rj2["audit_id"]  # different audits, but provenance is what we vary
    # Re-sign the same audit identity with only the engine version changed:
    a = _audit()
    s1, hh1, _ = _build_signed_json(a, _enhanced(), [], _report(engine_version="8.0.0"))
    s2, hh2, _ = _build_signed_json(a, _enhanced(), [], _report(engine_version="8.0.1"))
    assert hh1 != hh2, "export_hash must change when engine_version changes"
    assert s1["engine_version"] == "8.0.0"
    assert s2["engine_version"] == "8.0.1"


def test_export_hash_covers_rule_pack_hash():
    a = _audit()
    _, h1, _ = _build_signed_json(a, _enhanced(), [], _report(rule_pack_hash="a" * 64))
    _, h2, _ = _build_signed_json(a, _enhanced(), [], _report(rule_pack_hash="b" * 64))
    assert h1 != h2, "export_hash must change when rule_pack_hash changes"


def test_pre_provenance_report_signs_sentinel():
    a = _audit()
    rj, _, _ = _build_signed_json(
        a, _enhanced(), [], _report(engine_version=None, rule_pack_hash=None, matrix=None)
    )
    assert rj["engine_version"] == _PROVENANCE_UNAVAILABLE
    assert rj["rule_pack_hash"] == _PROVENANCE_UNAVAILABLE
    assert rj["compliance_matrix_version"] == _PROVENANCE_UNAVAILABLE
