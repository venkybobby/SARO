"""STORY-362 — buyer-facing adapter capability matrix.

This is the document a technical buyer uses to decide whether SARO covers their
stack, so the tests here are mostly about it being unable to overclaim: it is
derived from adapter behaviour, it states what is NOT supported, and prohibited
claim language cannot reach it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from generate_capability_matrix import (  # noqa: E402
    FIELDS,
    OUT,
    PROHIBITED_PHRASES,
    _check_language,
    _field_support,
    build_document,
)

from conformance.providers import REGISTERED_ADAPTERS  # noqa: E402

pytestmark = pytest.mark.integration


def test_matrix_file_is_current():
    """AC-1 freshness: the committed doc must match what the code produces."""
    assert OUT.exists(), "capability matrix missing — run scripts/generate_capability_matrix.py"
    assert OUT.read_text(encoding="utf-8") == build_document(), (
        "docs/adapter-capability-matrix.md is stale — regenerate it"
    )


def test_covers_all_three_adapters():
    doc = build_document()
    for name in ("Bedrock", "Azure OpenAI", "Vertex AI"):
        assert name in doc


# ── AC-2: no aspirational rows ──────────────────────────────────────────────


def test_unsupported_fields_are_marked_not_omitted():
    """A field the provider does not emit must appear as ❌, not vanish."""
    doc = build_document()
    assert "❌" in doc
    # Azure and Vertex emit no tool data on their standard schema.
    tools_row = [ln for ln in doc.splitlines() if ln.startswith("| Tool / function calls")][0]
    assert tools_row.count("❌") == 2, f"expected two providers without tool data: {tools_row}"


def test_limitations_section_is_populated():
    doc = build_document()
    assert "## Limitations — what SARO does NOT support today" in doc
    assert "- None recorded." not in doc, "limitations section is empty — suspicious"


def test_blank_result_disclaimer_is_present():
    """The single most misreadable thing about partial coverage."""
    doc = build_document()
    assert "Reading a blank result correctly" in doc
    assert "mistaken for a clean one" in doc
    assert "nothing to evaluate" in doc


def test_live_interception_is_explicitly_not_offered():
    doc = build_document()
    assert "Live / inline interception | ❌ not offered" in doc


def test_provider_caveats_reach_the_document():
    """Configuration-dependent support is stated, not implied by a tick."""
    doc = build_document()
    assert "Vertex AI — Model identity:" in doc
    assert "endpoint id" in doc
    assert "Azure OpenAI — Token counts:" in doc


# ── Derivation correctness ──────────────────────────────────────────────────


def test_field_support_reads_availability_not_the_value():
    """error_code is None on a SUCCESSFUL record; that is not 'unsupported'."""
    for adapter in REGISTERED_ADAPTERS:
        record = adapter.standard_schema_record()
        assert _field_support(record, "error_code") == "yes", (
            f"{adapter.display_name}: a successful sample record made error "
            "handling look unsupported"
        )


def test_matrix_reflects_actual_adapter_behaviour():
    """Spot-check the derivation against the adapters themselves."""
    by_name = {a.display_name: a.standard_schema_record() for a in REGISTERED_ADAPTERS}
    # Azure/Vertex standard schemas carry no tool data.
    assert _field_support(by_name["Azure OpenAI"], "tools") == "no"
    assert _field_support(by_name["Vertex AI"], "tools") == "no"
    # Bedrock does.
    assert _field_support(by_name["Bedrock"], "tools") == "yes"
    # Neither Azure nor Vertex reports a stop reason.
    for name in ("Azure OpenAI", "Vertex AI"):
        assert _field_support(by_name[name], "stop_reason") == "no"


def test_every_declared_field_appears_as_a_row():
    doc = build_document()
    for _, label in FIELDS:
        assert f"| {label} |" in doc, f"field {label!r} missing from the matrix"


# ── Language guardrails ─────────────────────────────────────────────────────


def test_generated_document_contains_no_prohibited_claim_language():
    assert _check_language(build_document()) == []


@pytest.mark.parametrize("phrase", PROHIBITED_PHRASES)
def test_language_check_would_catch_each_prohibited_phrase(phrase):
    """The guardrail must actually fire — a check that never trips is decoration."""
    assert _check_language(f"SARO is {phrase} for this workload.") == [phrase]


def test_committed_document_passes_the_language_check():
    assert _check_language(OUT.read_text(encoding="utf-8")) == []


# ── AC-3: discoverability ───────────────────────────────────────────────────


def test_linked_from_compliance_hub_and_adapter_design():
    """No root README exists in this repo (recorded as PREMISE-UNVERIFIED);
    the matrix is linked from the two real entry points instead."""
    assert not (ROOT / "README.md").exists(), (
        "a root README now exists — link the capability matrix from it and "
        "update this test"
    )
    hub = (ROOT / "compliance" / "README.md").read_text(encoding="utf-8")
    design = (ROOT / "docs" / "adapter-design.md").read_text(encoding="utf-8")
    assert "adapter-capability-matrix" in hub
    assert "adapter-capability-matrix" in design
