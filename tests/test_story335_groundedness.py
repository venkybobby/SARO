"""STORY-335 — Runtime groundedness via non-LLM methods.

Groundedness must run in the product path with zero calls to any third-party
hosted model API (the locked claim, enforced by STORY-336). It scores claims by
retrieval-overlap + citation matching: every flagged claim references the source
span it failed to match.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grc.checks import CheckContext
from grc.checks.groundedness import (
    assess_groundedness,
    groundedness_check,
)
from grc.guards.external_model import scan_paths

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]
GROUNDEDNESS_SRC = REPO_ROOT / "grc" / "checks" / "groundedness.py"


def _ctx(**over) -> CheckContext:
    base = dict(output_id="out-1", system_id="sys-1")
    base.update(over)
    return CheckContext(**base)


# --- AC: unsupported flagged, supported passes ------------------------------


def test_supported_concrete_claim_passes() -> None:
    f = groundedness_check(
        _ctx(
            output_text="Studies show the policy covers 100% of flood damage.",
            retrieved_context="Independent studies show the policy covers 100% of flood damage and fire damage.",
        )
    )
    assert f.status == "pass"


def test_unsupported_claim_is_flagged() -> None:
    f = groundedness_check(
        _ctx(
            output_text="This treatment cures the disease in 100% of patients.",
            retrieved_context="The brochure lists office hours and contact details.",
        )
    )
    assert f.status == "concern"
    assert f.remediation


# --- AC: each flagged claim references the source span it failed to match ----


def test_unsupported_claim_cites_nearest_span() -> None:
    output = "The drug guarantees a 90% cure rate for all patients."
    context = (
        "The label notes common side effects. "
        "A small trial reported a 12% response in some patients."
    )
    report = assess_groundedness(output, context)
    unsupported = report.unsupported
    assert unsupported, "the guarantee claim should be unsupported"
    a = unsupported[0]
    # The cited span is a real span drawn from the supplied context...
    assert a.nearest_span in context
    # ...and it is the closest one (the patients/response sentence), yet below
    # the support threshold.
    assert "response" in a.nearest_span
    assert a.overlap < 0.5
    # The finding surfaces that span to the auditor.
    f = groundedness_check(_ctx(output_text=output, retrieved_context=context))
    assert a.nearest_span in f.facts


def test_supported_claim_traces_to_supporting_span() -> None:
    output = "The policy guarantees coverage for 100% of flood claims."
    context = (
        "Section 2 is unrelated boilerplate. "
        "The policy guarantees coverage for 100% of flood claims filed on time."
    )
    report = assess_groundedness(output, context)
    assert report.supported, "claim should trace to a supporting span"
    a = report.supported[0]
    assert a.supported and a.overlap >= 0.5
    assert "flood claims" in a.nearest_span


def test_empty_context_flags_marked_claim_with_empty_span() -> None:
    report = assess_groundedness("Proven to work in 100% of cases.", "")
    assert report.unsupported
    assert report.unsupported[0].nearest_span == ""


def test_zero_overlap_context_still_cites_nearest_span() -> None:
    # Spans exist but none overlap: the claim still cites the nearest span (not "")
    # so an auditor always sees the context it failed to match.
    report = assess_groundedness(
        "Proven to cure 100% of cases.", "Office hours are nine to five."
    )
    a = report.unsupported[0]
    assert a.nearest_span == "Office hours are nine to five."
    assert a.overlap == 0.0


def test_no_concrete_claim_passes() -> None:
    # A sentence with no concrete-claim marker is not scrutinised.
    report = assess_groundedness("We received your message.", "Unrelated context.")
    assert report.assessments == []
    assert groundedness_check(_ctx(output_text="We received your message.")).status == (
        "pass"
    )


# --- AC: zero external-model calls on the groundedness path (links STORY-336) -


def test_groundedness_path_makes_no_external_model_call() -> None:
    violations = scan_paths(
        [GROUNDEDNESS_SRC], repo_root=REPO_ROOT, allowlist=frozenset()
    )
    assert violations == [], (
        f"groundedness must not reach an external model: {violations}"
    )


def test_module_no_longer_advertises_llm_judge_pass() -> None:
    # STORY-335 supersedes the STORY-309 LLM-as-judge sub-check. A historical note
    # that it was superseded is fine; advertising an *optional LLM pass* as current
    # behaviour (the removed STORY-309 docstring) or importing a provider is not.
    src = GROUNDEDNESS_SRC.read_text(encoding="utf-8").lower()
    assert "optional llm-as-judge pass" not in src
    assert "anthropic" not in src
    assert "import openai" not in src
