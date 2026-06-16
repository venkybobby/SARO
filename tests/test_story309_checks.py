"""STORY-309 — Automated output checks tests.

AC coverage:
- Each of the five checks runs and returns a structured finding (pass/concern).
- Groundedness flags an unsupported claim; passes a supported one.
- Leakage detects a planted PII string; passes a clean output.
- Prohibited-use fails an output outside the registry purpose.
- Regulatory-claim routes any compliance/legal claim through STORY-317.
- All five run within the orchestrator (covered in test_story308).
"""

from __future__ import annotations

import pytest

from grc.checks import CheckContext, run_all_checks
from grc.checks.bias import bias_check
from grc.checks.groundedness import groundedness_check
from grc.checks.leakage import leakage_check
from grc.checks.prohibited_use import prohibited_use_check
from grc.checks.regulatory_claim import regulatory_claim_check

pytestmark = pytest.mark.unit


def _ctx(**over) -> CheckContext:
    base = dict(output_id="out-1", system_id="sys-1")
    base.update(over)
    return CheckContext(**base)


# ── Groundedness ──
def test_groundedness_passes_supported_claim() -> None:
    ctx = _ctx(
        output_text="The policy covers flood damage.",
        retrieved_context="The policy covers flood damage and fire damage.",
    )
    assert groundedness_check(ctx).status == "pass"


def test_groundedness_flags_unsupported_claim() -> None:
    ctx = _ctx(
        output_text="This treatment cures the disease in 100% of patients.",
        retrieved_context="The brochure lists office hours and contact details.",
    )
    f = groundedness_check(ctx)
    assert f.status == "concern"
    assert f.remediation


# ── Leakage ──
def test_leakage_passes_clean_output() -> None:
    assert (
        leakage_check(_ctx(output_text="Your claim has been received.")).status
        == "pass"
    )


def test_leakage_detects_pii() -> None:
    f = leakage_check(_ctx(output_text="The applicant SSN is 123-45-6789."))
    assert f.status == "concern"
    assert "123-45-6789" not in f.facts  # redacted before egress


def test_leakage_detects_secret() -> None:
    f = leakage_check(_ctx(output_text="api_key=sk-abcdef0123456789abcdef"))
    assert f.status == "concern"


# ── Bias ──
def test_bias_passes_neutral_output() -> None:
    assert (
        bias_check(
            _ctx(output_text="The claim was approved based on policy terms.")
        ).status
        == "pass"
    )


def test_bias_flags_protected_attribute_decision() -> None:
    f = bias_check(_ctx(output_text="The loan was denied because of her gender."))
    assert f.status == "concern"


# ── Prohibited use ──
def test_prohibited_use_passes_in_scope() -> None:
    f = prohibited_use_check(
        _ctx(
            output_text="The insurance claim was triaged and routed to an adjuster.",
            registry_purpose="Triage inbound insurance claims",
        )
    )
    assert f.status == "pass"


def test_prohibited_use_flags_out_of_scope() -> None:
    f = prohibited_use_check(
        _ctx(
            output_text="Here is a working ransomware payload script you requested.",
            registry_purpose="Triage inbound insurance claims",
        )
    )
    assert f.status == "concern"


def test_prohibited_use_no_purpose_passes() -> None:
    assert prohibited_use_check(_ctx(output_text="anything")).status == "pass"


# ── Regulatory claim ──
def test_regulatory_claim_passes_non_claim() -> None:
    assert (
        regulatory_claim_check(_ctx(output_text="Here is your summary.")).status
        == "pass"
    )


def test_regulatory_claim_verified_citation_passes() -> None:
    f = regulatory_claim_check(
        _ctx(
            output_text="This supports evidence for EU AI Act Article 9 risk management."
        )
    )
    assert f.status == "pass"
    assert any(m["status"] == "VERIFIED" for m in f.framework_mapping)


def test_regulatory_claim_unverifiable_citation_flagged() -> None:
    f = regulatory_claim_check(
        _ctx(output_text="This is certified under EU AI Act Article 99.")
    )
    assert f.status == "concern"
    assert any(m["status"] == "UNVERIFIED" for m in f.framework_mapping)


def test_regulatory_claim_without_citation_flagged() -> None:
    f = regulatory_claim_check(
        _ctx(output_text="This system is fully compliant and certified.")
    )
    assert f.status == "concern"


# ── Uniform interface / run_all ──
def test_run_all_checks_returns_five_findings() -> None:
    findings = run_all_checks(_ctx(output_text="Your claim was received."))
    assert len(findings) == 5
    names = {f.check for f in findings}
    assert len(names) == 5  # all distinct
    for f in findings:
        assert f.status in ("pass", "concern")
