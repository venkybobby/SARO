"""STORY-403 — Edge-Redaction Reference Sidecar tests.

AC coverage (see specs/stories/STORY-403.md):
- AC-1 patterns cover HIPAA-18 classes, driven by an injected catalog (no baked list)
- AC-2 catalog config-injected: disabling/adding a class changes behavior, no code change
- AC-3 SLIs per batch: coverage, residual-identifier rate, drift vs baseline
- AC-4 output de-identified; original never retained/mutated
- AC-5 Expert Determination is a named hook that raises cleanly

Invariant guard: deterministic/rule-based only — no external API/model; SLIs describe
measured coverage, never "guaranteed removal" (ADR-004).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

from services import edge_redaction
from services.edge_redaction import FieldClass

# Fixtures dir is path-loaded (tests/ is not a package).
sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures"))
from synthetic_phi import (  # noqa: E402
    labeled_text_sample,
    reference_safe_harbor_catalog,
    structured_phi_record,
)


# ---------------------------------------------------------------------------
# AC-1 — HIPAA-18 coverage via the injected catalog
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_reference_catalog_enumerates_all_18_hipaa_categories() -> None:
    catalog = reference_safe_harbor_catalog()
    categories = {fc.hipaa_category for fc in catalog}
    assert categories == set(range(1, 19)), (
        f"missing HIPAA categories: {set(range(1, 19)) - categories}"
    )


@pytest.mark.unit
def test_each_text_identifier_class_redacted() -> None:
    sample = labeled_text_sample()
    catalog = reference_safe_harbor_catalog()
    result = edge_redaction.redact_text(sample["text"], catalog)
    # Every known identifier value must be absent from the de-identified output.
    for values in sample["expected_identifiers"].values():
        for value in values:
            assert value not in result.output, (
                f"identifier {value!r} survived redaction"
            )


@pytest.mark.unit
def test_residual_rate_below_threshold_on_fixture() -> None:
    sample = labeled_text_sample()
    catalog = reference_safe_harbor_catalog()
    result = edge_redaction.redact_text(sample["text"], catalog)
    assert result.sli.residual_rate <= 0.05, (
        f"residual rate {result.sli.residual_rate} over threshold"
    )


# ---------------------------------------------------------------------------
# AC-1/AC-2 — no baked master list; catalog drives behavior
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_empty_catalog_redacts_nothing() -> None:
    """Proves there is no hardcoded master list inside SARO — with no catalog, the
    component applies no patterns and returns the input unchanged."""
    text = "Email jdoe@example.com SSN 123-45-6789"
    result = edge_redaction.redact_text(text, [])
    assert result.output == text
    assert result.sli.identifiers_redacted == 0


@pytest.mark.unit
def test_disabling_a_class_is_reflected_in_output() -> None:
    text = "Reach me at jdoe@example.com"
    catalog = [
        FieldClass(
            name="email",
            hipaa_category=6,
            kind="regex",
            pattern=r"[\w.+-]+@[\w-]+\.[\w.-]+",
        )
    ]
    assert "jdoe@example.com" not in edge_redaction.redact_text(text, catalog).output
    # Disable the same class → behavior changes with no code change.
    catalog[0].enabled = False
    assert "jdoe@example.com" in edge_redaction.redact_text(text, catalog).output


@pytest.mark.unit
def test_adding_a_new_class_is_honored() -> None:
    text = "Employee badge BADGE-99812 entered."
    catalog = [
        FieldClass(name="badge", hipaa_category=18, kind="regex", pattern=r"BADGE-\d+")
    ]
    result = edge_redaction.redact_text(text, catalog)
    assert "BADGE-99812" not in result.output and result.sli.identifiers_redacted == 1


# ---------------------------------------------------------------------------
# AC-3 — SLI math on a controlled fixture
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sli_math_full_coverage() -> None:
    text = "a jdoe@example.com b 123-45-6789 c"
    catalog = [
        FieldClass(
            name="email",
            hipaa_category=6,
            kind="regex",
            pattern=r"[\w.+-]+@[\w-]+\.[\w.-]+",
        ),
        FieldClass(
            name="ssn", hipaa_category=7, kind="regex", pattern=r"\d{3}-\d{2}-\d{4}"
        ),
    ]
    result = edge_redaction.redact_text(text, catalog, baseline_coverage=0.8)
    assert result.sli.identifiers_redacted == 2
    assert result.sli.residual_identifiers == 0
    assert result.sli.coverage == 1.0
    assert result.sli.residual_rate == 0.0
    assert result.sli.drift == pytest.approx(0.2)  # coverage - baseline


@pytest.mark.unit
def test_sli_math_partial_coverage_when_class_disabled() -> None:
    text = "jdoe@example.com and 123-45-6789"
    catalog = [
        FieldClass(
            name="email",
            hipaa_category=6,
            kind="regex",
            pattern=r"[\w.+-]+@[\w-]+\.[\w.-]+",
        ),
        FieldClass(
            name="ssn",
            hipaa_category=7,
            kind="regex",
            pattern=r"\d{3}-\d{2}-\d{4}",
            enabled=False,
        ),
    ]
    result = edge_redaction.redact_text(text, catalog)
    # email redacted, ssn left → residual found on re-scan with the *full* catalog patterns.
    assert result.sli.identifiers_redacted == 1
    assert result.sli.residual_identifiers == 1
    assert result.sli.coverage == pytest.approx(0.5)
    assert result.sli.residual_rate == pytest.approx(0.5)


@pytest.mark.unit
def test_drift_none_without_baseline() -> None:
    result = edge_redaction.redact_text("no phi here", [])
    assert result.sli.drift is None


@pytest.mark.unit
def test_no_signal_coverage_is_none_not_fabricated() -> None:
    """S4: nothing catalog-detectable present → coverage/residual_rate/drift are None,
    so an empty batch can't masquerade as perfect coverage / positive drift."""
    catalog = [
        FieldClass(
            name="ssn", hipaa_category=7, kind="regex", pattern=r"\d{3}-\d{2}-\d{4}"
        )
    ]
    result = edge_redaction.redact_text("nothing here", catalog, baseline_coverage=0.9)
    assert result.sli.coverage is None
    assert result.sli.residual_rate is None
    assert result.sli.drift is None


@pytest.mark.unit
def test_overlapping_patterns_count_one_identifier() -> None:
    """M2: a URL containing an email is one identifier, not two — no double-count."""
    text = "see https://user@host.example.com/x"
    catalog = [
        FieldClass(
            name="email",
            hipaa_category=6,
            kind="regex",
            pattern=r"[\w.+-]+@[\w-]+\.[\w.-]+",
        ),
        FieldClass(
            name="url", hipaa_category=14, kind="regex", pattern=r"https?://[^\s]+"
        ),
    ]
    result = edge_redaction.redact_text(text, catalog)
    assert result.sli.identifiers_redacted == 1
    assert "user@host.example.com" not in result.output


# ---------------------------------------------------------------------------
# AC-4 — structured record redaction; original not retained/mutated
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_structured_field_redacted_wholesale() -> None:
    record, phi_fields = structured_phi_record()
    catalog = reference_safe_harbor_catalog()
    result = edge_redaction.redact_record(record, catalog)
    for f in phi_fields:
        assert str(record[f]) not in str(result.output.get(f, "")), (
            f"field {f} not redacted"
        )


@pytest.mark.unit
def test_original_record_not_mutated() -> None:
    record, _ = structured_phi_record()
    snapshot = dict(record)
    edge_redaction.redact_record(record, reference_safe_harbor_catalog())
    assert record == snapshot, "redact_record mutated the caller's original record"


@pytest.mark.unit
def test_disabled_field_class_counts_as_residual() -> None:
    """M1: a declared PHI field whose class is disabled is left in place AND counted as
    residual (a measured gap, not a silent blind spot)."""
    record = {"patient_name": "Jane Roe"}
    catalog = [
        FieldClass(
            name="name",
            hipaa_category=1,
            kind="field",
            field_name="patient_name",
            enabled=False,
        )
    ]
    result = edge_redaction.redact_record(record, catalog)
    assert result.output["patient_name"] == "Jane Roe"  # left in place
    assert result.sli.residual_identifiers == 1
    assert result.sli.coverage == 0.0


@pytest.mark.unit
def test_nested_record_phi_is_redacted_and_not_aliased() -> None:
    """F2: nested dict/list PHI is redacted, and nested objects in the output are fresh
    copies (no aliasing back to the caller's original)."""
    record = {"meta": {"ssn": "123-45-6789"}, "items": ["call 123-45-6789"]}
    catalog = [
        FieldClass(
            name="ssn", hipaa_category=7, kind="regex", pattern=r"\d{3}-\d{2}-\d{4}"
        )
    ]
    result = edge_redaction.redact_record(record, catalog)
    assert "123-45-6789" not in str(result.output)
    assert result.output["meta"] is not record["meta"], (
        "nested dict aliased to original"
    )
    assert result.sli.identifiers_redacted == 2


@pytest.mark.unit
def test_nonstring_scalar_field_not_aliased() -> None:
    record = {"vitals": {"hr": 72}}
    result = edge_redaction.redact_record(record, [])
    assert result.output == record
    assert result.output["vitals"] is not record["vitals"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_pattern",
    [r"(a+)+$", "x" * (edge_redaction.MAX_PATTERN_LENGTH + 1)],
)
def test_catalog_validation_rejects_dangerous_patterns(bad_pattern) -> None:
    """F1: over-long or catastrophic-backtracking catalog patterns are rejected up front."""
    catalog = [
        FieldClass(name="bad", hipaa_category=18, kind="regex", pattern=bad_pattern)
    ]
    with pytest.raises(ValueError):
        edge_redaction.redact_text("anything", catalog)


# ---------------------------------------------------------------------------
# AC-5 — Expert Determination hook
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_expert_determination_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        edge_redaction.expert_determination("anything")


# ---------------------------------------------------------------------------
# Invariant guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_external_api_or_model_in_service() -> None:
    import inspect

    src = inspect.getsource(edge_redaction)
    for needle in ("requests", "httpx", "urllib", "anthropic", "openai", "socket"):
        assert needle not in src, (
            f"edge_redaction must not reference {needle} (local-only invariant)"
        )


@pytest.mark.unit
def test_no_overclaim_language_in_service() -> None:
    import inspect

    src = inspect.getsource(edge_redaction).lower()
    for phrase in (
        "guarantee",
        "guarantees removal",
        "ensures removal",
        "fully removes",
    ):
        assert phrase not in src, f"ADR-004: edge_redaction must not claim {phrase!r}"
