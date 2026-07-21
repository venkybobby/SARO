"""STORY-361 — cross-adapter conformance suite.

One scenario set, instantiated against every registered adapter. The suite's
job is to make "supports Azure/Vertex" falsifiable, so the tests here are as
much about the suite's own integrity (an adapter cannot dodge a scenario, a gap
cannot masquerade as a pass) as about the adapters.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conformance.harness import (  # noqa: E402
    SCENARIO_INTENT,
    Scenario,
    Support,
    run_conformance,
    universal_invariants,
)
from conformance.providers import REGISTERED_ADAPTERS  # noqa: E402

pytestmark = pytest.mark.integration

_REPORT = run_conformance(REGISTERED_ADAPTERS)
_CASES = [(a.display_name, s) for a in REGISTERED_ADAPTERS for s in Scenario]


@pytest.mark.parametrize(
    "adapter_name,scenario",
    _CASES,
    ids=[f"{n}-{s.value}" for n, s in _CASES],
)
def test_adapter_conforms(adapter_name: str, scenario: Scenario):
    """The parametrized matrix: every adapter × every scenario."""
    result = next(
        r for r in _REPORT.results
        if r.display_name == adapter_name and r.scenario is scenario
    )
    assert result.passed, (
        f"{adapter_name} / {scenario.value}: {result.detail}\n"
        f"intent: {SCENARIO_INTENT[scenario]}"
    )


# ── Suite integrity: the tests that keep the suite honest ───────────────────


def test_every_adapter_answers_every_scenario():
    """No silent omissions — an adapter must return an outcome for each scenario."""
    for adapter in REGISTERED_ADAPTERS:
        covered = {
            r.scenario for r in _REPORT.results if r.display_name == adapter.display_name
        }
        assert covered == set(Scenario), (
            f"{adapter.display_name} did not answer: {sorted(s.value for s in set(Scenario) - covered)}"
        )


def test_all_three_adapters_are_registered():
    names = {a.display_name for a in REGISTERED_ADAPTERS}
    assert names == {"Bedrock", "Azure OpenAI", "Vertex AI"}


def test_unsupported_declarations_carry_a_substantive_reason():
    """A gap must be explained, not merely asserted."""
    for r in _REPORT.gaps:
        assert len(r.reason.strip()) >= 20, (
            f"{r.display_name}/{r.scenario.value} declared unsupported without a real reason"
        )


def test_gaps_are_reported_as_gaps_not_passes():
    """The matrix must never render a coverage gap as a tick."""
    md = _REPORT.to_markdown()
    assert "⚠️ n/a" in md, "expected at least one declared gap in the current matrix"
    for r in _REPORT.gaps:
        assert r.reason in md, "every gap's reason must appear in the report"


def test_conditional_support_is_not_rendered_as_full_support():
    """A buyer seeing ✅ would assume it works on the logs they already have."""
    md = _REPORT.to_markdown()
    assert "◐ conditional" in md
    assert "Conditional support (preconditions apply)" in md
    for r in _REPORT.conditionals:
        assert r.reason in md, "every precondition must be stated in the report"


def test_conditional_declarations_carry_their_precondition():
    for r in _REPORT.conditionals:
        assert len(r.reason.strip()) >= 20


def test_known_conditionals_are_exactly_the_expected_ones():
    """Tool-scope on Azure/Vertex needs an enriched export — pinned so a future
    change cannot quietly upgrade it to full support."""
    conditional = {(r.display_name, r.scenario.value) for r in _REPORT.conditionals}
    assert conditional == {
        ("Azure OpenAI", "tool_scope_violation"),
        ("Vertex AI", "tool_scope_violation"),
    }, f"conditional support changed: {sorted(conditional)}"


def test_known_gaps_are_exactly_the_expected_ones():
    """Pins current coverage. A NEW gap must be a deliberate, reviewed change —
    this is what stops an adapter quietly declaring its way out of a scenario."""
    gaps = {(r.display_name, r.scenario.value) for r in _REPORT.gaps}
    assert gaps == {
        ("Azure OpenAI", "incomplete_observation"),
        ("Vertex AI", "incomplete_observation"),
    }, f"coverage gaps changed: {sorted(gaps)}"


def test_bedrock_supports_every_scenario():
    """Adapter #1 is the reference: full coverage is what the others are measured against."""
    bedrock = [r for r in _REPORT.results if r.display_name == "Bedrock"]
    assert all(r.support is Support.SUPPORTED for r in bedrock)
    assert all(r.passed for r in bedrock)


def test_no_failures_anywhere():
    assert _REPORT.failures == [], [
        (r.display_name, r.scenario.value, r.detail) for r in _REPORT.failures
    ]


# ── Universal invariants, checked on every produced record ──────────────────


def test_universal_invariants_hold_for_every_record():
    """INV-2 contract shape, provenance completeness, tz-aware timestamps."""
    # Results deliberately carry no record (the report is serializable), so the
    # scenarios are rebuilt here to inspect the records themselves.
    checked = 0
    for adapter in REGISTERED_ADAPTERS:
        for scenario in Scenario:
            outcome = adapter.build(scenario)
            if outcome.record is None:
                continue
            problems = universal_invariants(outcome.record)
            assert not problems, f"{adapter.display_name}/{scenario.value}: {problems}"
            checked += 1
    assert checked >= 12, f"only {checked} records checked — suite may be vacuous"


def test_records_are_deterministic_across_runs():
    """Same input twice ⇒ identical record. Attestations depend on this."""
    for adapter in REGISTERED_ADAPTERS:
        first = adapter.build(Scenario.HAPPY_PATH).record
        second = adapter.build(Scenario.HAPPY_PATH).record
        assert first is not None and second is not None
        assert first.model_dump_json() == second.model_dump_json(), adapter.display_name


def test_report_serializes_to_the_documented_schema():
    data = _REPORT.to_dict()
    assert data["schema"] == "saro.conformance.v1"
    assert data["summary"]["adapters"] == 3
    assert data["summary"]["checks"] == 3 * len(Scenario)
    assert data["summary"]["failed"] == 0
    assert data["summary"]["coverage_gaps"] == len(_REPORT.gaps)
