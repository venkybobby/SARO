"""STORY-328 — Audit-result JSON contract tests.

AC coverage:
- A valid result instance passes validation.
- A PASS finding with MISSING evidence is rejected (rule 1).
- A FAIL / CONDITIONAL finding with no remediation is rejected (rule 2).
- A result with a Critical FAIL but gate_recommendation != NO_GO is rejected (rule 3).
"""

from __future__ import annotations

import pytest

from grc.contract import (
    DISPOSITIONS,
    GATE_RECOMMENDATIONS,
    RISK_BANDS,
    SCHEMA_VERSION,
    ContractError,
    is_valid_audit_result,
    validate_audit_result,
)

pytestmark = pytest.mark.unit


def _finding(**overrides) -> dict:
    base: dict = {
        "id": "f1",
        "check": "groundedness",
        "disposition": "PASS",
        "risk": {"likelihood": 1, "impact": 2, "score": 2, "band": "LOW"},
        "evidence": {"status": "LINKED", "evidence_ids": ["ev-1"]},
        "remediation": None,
        "framework_mapping": [],
        "facts": "Output claim X is supported by retrieved context chunk 3.",
        "assessment": "No hallucination detected.",
        "scope_change_flag": False,
    }
    base.update(overrides)
    return base


def _result(**overrides) -> dict:
    base = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": "grc-policy-1.0.0",
        "audited_output_id": "out-123",
        "system_id": "sys-1",
        "generated_at": "2026-06-16T03:00:00Z",
        "findings": [_finding()],
        "gate_recommendation": "GO",
    }
    base.update(overrides)
    return base


def test_valid_result_passes() -> None:
    assert validate_audit_result(_result()) == _result()
    assert is_valid_audit_result(_result()) is True


def test_pass_with_missing_evidence_rejected() -> None:
    bad = _result(
        findings=[_finding(disposition="PASS", evidence={"status": "MISSING"})]
    )
    with pytest.raises(ContractError):
        validate_audit_result(bad)


def test_fail_without_remediation_rejected() -> None:
    bad = _result(
        findings=[
            _finding(
                disposition="FAIL",
                risk={"likelihood": 3, "impact": 3, "score": 9, "band": "MODERATE"},
                evidence={"status": "LINKED", "evidence_ids": ["ev-1"]},
                remediation=None,
            )
        ],
        gate_recommendation="GO_WITH_CONDITIONS",
    )
    with pytest.raises(ContractError, match="remediation"):
        validate_audit_result(bad)


def test_conditional_without_remediation_rejected() -> None:
    bad = _result(
        findings=[
            _finding(
                disposition="CONDITIONAL",
                risk={"likelihood": 2, "impact": 3, "score": 6, "band": "LOW"},
                evidence={"status": "LINKED", "evidence_ids": ["ev-1"]},
                remediation="",  # empty string is not a valid remediation
            )
        ],
        gate_recommendation="GO_WITH_CONDITIONS",
    )
    with pytest.raises(ContractError):
        validate_audit_result(bad)


def test_fail_with_remediation_accepted() -> None:
    ok = _result(
        findings=[
            _finding(
                disposition="FAIL",
                risk={"likelihood": 3, "impact": 3, "score": 9, "band": "MODERATE"},
                evidence={"status": "LINKED", "evidence_ids": ["ev-1"]},
                remediation="Add a grounding citation for claim X before release.",
            )
        ],
        gate_recommendation="GO_WITH_CONDITIONS",
    )
    assert is_valid_audit_result(ok) is True


def test_critical_fail_without_no_go_rejected() -> None:
    bad = _result(
        findings=[
            _finding(
                disposition="FAIL",
                risk={"likelihood": 5, "impact": 5, "score": 25, "band": "CRITICAL"},
                evidence={"status": "LINKED", "evidence_ids": ["ev-1"]},
                remediation="Block release; remove the unsafe instruction.",
            )
        ],
        gate_recommendation="GO_WITH_CONDITIONS",  # must be NO_GO
    )
    with pytest.raises(ContractError):
        validate_audit_result(bad)


def test_critical_fail_with_no_go_accepted() -> None:
    ok = _result(
        findings=[
            _finding(
                disposition="FAIL",
                risk={"likelihood": 5, "impact": 5, "score": 25, "band": "CRITICAL"},
                evidence={"status": "LINKED", "evidence_ids": ["ev-1"]},
                remediation="Block release; remove the unsafe instruction.",
            )
        ],
        gate_recommendation="NO_GO",
    )
    assert is_valid_audit_result(ok) is True


def test_facts_and_assessment_required() -> None:
    f = _finding()
    del f["facts"]
    with pytest.raises(ContractError, match="facts"):
        validate_audit_result(_result(findings=[f]))


def test_enums_sourced_from_schema() -> None:
    assert DISPOSITIONS == (
        "PASS",
        "CONDITIONAL",
        "FAIL",
        "EVIDENCE_GAP",
        "OUT_OF_SCOPE",
    )
    assert RISK_BANDS == ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert GATE_RECOMMENDATIONS == ("GO", "GO_WITH_CONDITIONS", "NO_GO")


def test_unknown_disposition_rejected() -> None:
    bad = _result(findings=[_finding(disposition="MAYBE")])
    with pytest.raises(ContractError):
        validate_audit_result(bad)


def test_additional_properties_rejected() -> None:
    bad = _result(unexpected="x")
    with pytest.raises(ContractError):
        validate_audit_result(bad)
