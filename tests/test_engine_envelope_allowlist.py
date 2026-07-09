"""STORY-411 — envelope-only model-allowlist evaluation in engine.run_output_audit.

Covers:
  AC-1.1  off-allowlist modelId -> exactly one finding, category = Governance & Compliance
  AC-1.2  on-allowlist modelId -> no envelope finding; content evaluation unaffected
  AC-1.3  deterministic and stateless: same input + same rule-pack version = same
          finding, byte-stable
  AC-2.2  finding records observed modelId, rule id, rule-pack version, requestId
  AC-3.1  finding language is observable-only (ADR-004): no "unauthorized"/"breach"/
          intent language
  Backward compat: no metadata param -> no-op, existing callers unaffected
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from engine import SARoEngine

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_OFF_ALLOWLIST_MODEL = "anthropic.claude-instant-v1"
_ON_ALLOWLIST_MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
_BENIGN_OUTPUT = "The quarterly report was generated successfully with no issues."


def _engine_obj():
    db = _Session()
    return SARoEngine(db)


@pytest.mark.unit
def test_off_allowlist_model_fires_exactly_one_governance_finding():
    eng = _engine_obj()
    eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="Summarize the report.",
        source_model="claude",
        metadata={"modelId": _OFF_ALLOWLIST_MODEL, "requestId": "req-123"},
    )
    findings = [
        f for f in eng.get_sample_findings() if f["domain"] == "Governance & Compliance"
    ]
    assert len(findings) == 1


@pytest.mark.unit
def test_on_allowlist_model_fires_no_envelope_finding():
    eng = _engine_obj()
    eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="Summarize the report.",
        source_model="claude",
        metadata={"modelId": _ON_ALLOWLIST_MODEL, "requestId": "req-456"},
    )
    findings = [
        f for f in eng.get_sample_findings() if f["domain"] == "Governance & Compliance"
    ]
    assert findings == []


@pytest.mark.unit
def test_no_metadata_is_a_no_op_backward_compat():
    eng = _engine_obj()
    report = eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="Summarize the report.",
        source_model="claude",
    )
    assert report.status == "completed"
    findings = [
        f for f in eng.get_sample_findings() if f["domain"] == "Governance & Compliance"
    ]
    assert findings == []


@pytest.mark.unit
def test_deterministic_same_input_same_finding():
    eng = _engine_obj()
    metadata = {"modelId": _OFF_ALLOWLIST_MODEL, "requestId": "req-789"}
    eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="p",
        source_model="claude",
        metadata=metadata,
    )
    first_traces = [
        t for t in eng.get_traces() if t["check_name"] == "Governance & Compliance"
    ]

    eng2 = _engine_obj()
    eng2.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="p",
        source_model="claude",
        metadata=metadata,
    )
    second_traces = [
        t for t in eng2.get_traces() if t["check_name"] == "Governance & Compliance"
    ]

    assert len(first_traces) == 1 and len(second_traces) == 1
    t1, t2 = first_traces[0], second_traces[0]
    assert t1["result"] == t2["result"] == "flagged"
    assert t1["reason"] == t2["reason"]
    assert t1["detail_json"] == t2["detail_json"]


@pytest.mark.unit
def test_finding_records_model_id_rule_id_version_and_request_id():
    eng = _engine_obj()
    eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="p",
        source_model="claude",
        metadata={"modelId": _OFF_ALLOWLIST_MODEL, "requestId": "req-abc"},
    )
    trace = next(
        t for t in eng.get_traces() if t["check_name"] == "Governance & Compliance"
    )
    assert trace["result"] == "flagged"
    detail = trace["detail_json"]["flagged_signals"][0]["detail"]
    assert detail["observed_model_id"] == _OFF_ALLOWLIST_MODEL
    assert detail["rule_id"] == "ENV-MODEL-ALLOWLIST-1"
    assert detail["rule_pack_version"] == "1.0.0"
    assert detail["request_id"] == "req-abc"


@pytest.mark.unit
def test_oversized_model_id_and_request_id_are_truncated_before_storage():
    """security-auditor (STORY-411 verify): a malformed/adversarial log record
    could carry an oversized modelId/requestId — cap before storage."""
    eng = _engine_obj()
    oversized_model_id = "anthropic.claude-instant-v1-" + ("x" * 1000)
    oversized_request_id = "r" * 1000
    eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="p",
        source_model="claude",
        metadata={"modelId": oversized_model_id, "requestId": oversized_request_id},
    )
    finding = next(
        f for f in eng.get_sample_findings() if f["domain"] == "Governance & Compliance"
    )
    trace = next(
        t for t in eng.get_traces() if t["check_name"] == "Governance & Compliance"
    )
    detail = trace["detail_json"]["flagged_signals"][0]["detail"]
    assert len(detail["observed_model_id"]) == 256
    assert len(detail["request_id"]) == 256
    assert len(finding["sample_id"]) == 256


@pytest.mark.unit
def test_finding_language_is_observable_only_adr_004():
    eng = _engine_obj()
    eng.run_output_audit(
        audit_id=uuid.uuid4(),
        raw_output=_BENIGN_OUTPUT,
        prompt="p",
        source_model="claude",
        metadata={"modelId": _OFF_ALLOWLIST_MODEL, "requestId": "req-def"},
    )
    finding = next(
        f for f in eng.get_sample_findings() if f["domain"] == "Governance & Compliance"
    )
    text = finding["matched_text_fragment"].lower()
    for forbidden in ("unauthorized", "breach", "attack", "malicious", "compromise"):
        assert forbidden not in text
    assert (
        finding["matched_text_fragment"]
        == "Model not on approved allowlist for this tenant"
    )
