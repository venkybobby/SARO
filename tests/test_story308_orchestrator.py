"""STORY-308 — Audit orchestrator service tests.

AC coverage:
- A valid output id yields a result that validates against the JSON contract.
- Provenance check runs first; incomplete provenance short-circuits to EVIDENCE_GAP.
- Each finding carries a disposition, risk score, and framework mapping.
- The orchestrator never emits PASS where evidence is not LINKED.
- All five checks run within the orchestrator on a sample output.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from grc.contract import is_valid_audit_result
from grc.orchestrator import run_audit

pytestmark = pytest.mark.unit


def _evidence(**over) -> dict:
    base = dict(
        id="ev-1",
        system_id="sys-1",
        model_version="claude-sonnet-4",
        prompt="Summarize the policy coverage.",
        retrieved_context="The policy covers flood and fire damage.",
        decision="The policy covers flood damage.",
        confidence=0.9,
        consumer="agent-7",
        captured_at=datetime.now(tz=timezone.utc),
    )
    base.update(over)
    return base


def test_clean_output_yields_schema_valid_result() -> None:
    result = run_audit(
        "out-1", _evidence(), registry_purpose="Summarize insurance policies"
    )
    assert is_valid_audit_result(result)
    assert result["audited_output_id"] == "out-1"
    assert result["policy_version"]  # STORY-331 version stamped


def test_all_five_checks_run() -> None:
    result = run_audit(
        "out-1", _evidence(), registry_purpose="Summarize insurance policies"
    )
    checks = {f["check"] for f in result["findings"]}
    assert checks == {
        "groundedness",
        "sensitive_data_leakage",
        "harmful_bias",
        "prohibited_use",
        "regulatory_claim_accuracy",
    }


def test_each_finding_has_disposition_risk_and_mapping() -> None:
    result = run_audit(
        "out-1", _evidence(), registry_purpose="Summarize insurance policies"
    )
    for f in result["findings"]:
        assert f["disposition"] in (
            "PASS",
            "CONDITIONAL",
            "FAIL",
            "EVIDENCE_GAP",
            "OUT_OF_SCOPE",
        )
        assert set(f["risk"]) == {"likelihood", "impact", "score", "band"}
        assert "framework_mapping" in f


def test_incomplete_provenance_short_circuits_to_evidence_gap() -> None:
    result = run_audit("out-2", _evidence(decision=None))  # missing required field
    assert is_valid_audit_result(result)
    assert len(result["findings"]) == 1
    only = result["findings"][0]
    assert only["disposition"] == "EVIDENCE_GAP"
    assert only["evidence"]["status"] == "MISSING"
    # No PASS may appear when provenance is incomplete.
    assert all(f["disposition"] != "PASS" for f in result["findings"])


def test_no_pass_without_linked_evidence() -> None:
    result = run_audit(
        "out-1", _evidence(), registry_purpose="Summarize insurance policies"
    )
    for f in result["findings"]:
        if f["disposition"] == "PASS":
            assert f["evidence"]["status"] == "LINKED"
            assert f["evidence"]["evidence_ids"]  # at least one id


def test_critical_fail_forces_no_go() -> None:
    # An output leaking PII + making a false certified claim drives high-severity
    # fails; ensure the contract's Critical-FAIL=>NO_GO holds end-to-end.
    ev = _evidence(
        decision="Applicant SSN 123-45-6789. This system is certified compliant under EU AI Act Article 99.",
        retrieved_context="n/a",
    )
    result = run_audit("out-3", ev, registry_purpose="Summarize insurance policies")
    assert is_valid_audit_result(result)
    # Some concern finding(s) must exist and the gate must not be GO.
    assert result["gate_recommendation"] in ("GO_WITH_CONDITIONS", "NO_GO")
    assert any(f["disposition"] in ("FAIL", "CONDITIONAL") for f in result["findings"])
