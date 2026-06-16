"""STORY-306 — Provenance completeness gate tests.

AC coverage:
- An output with complete provenance is eligible for any disposition.
- An output missing any required provenance field returns EVIDENCE_GAP.
- It is impossible for the pipeline to emit PASS on incomplete provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from grc.evidence import REQUIRED_PROVENANCE_FIELDS
from grc.provenance import (
    EVIDENCE_GAP,
    ProvenanceError,
    enforce_can_pass,
    evaluate_provenance,
    is_provenance_complete,
    missing_provenance_fields,
)

pytestmark = pytest.mark.unit


def _complete(**over) -> dict:
    base = {
        "model_version": "claude-sonnet-4",
        "prompt": "Summarize the policy",
        "retrieved_context": "policy chunk 3",
        "decision": "Approved",
        "confidence": 0.0,  # 0.0 is a present value, not missing
        "consumer": "agent-7",
        "captured_at": datetime.now(tz=timezone.utc),
    }
    base.update(over)
    return base


def test_complete_provenance_is_eligible() -> None:
    result = evaluate_provenance(_complete())
    assert result.complete is True
    assert result.disposition is None
    assert is_provenance_complete(_complete()) is True


def test_each_missing_field_yields_evidence_gap() -> None:
    for field in REQUIRED_PROVENANCE_FIELDS:
        result = evaluate_provenance(_complete(**{field: None}))
        assert result.complete is False
        assert result.disposition == EVIDENCE_GAP
        assert field in result.missing


def test_zero_confidence_is_not_missing() -> None:
    assert missing_provenance_fields(_complete(confidence=0.0)) == []


def test_empty_string_counts_as_missing() -> None:
    assert "decision" in missing_provenance_fields(_complete(decision="  "))


def test_none_record_is_all_missing() -> None:
    assert set(missing_provenance_fields(None)) == set(REQUIRED_PROVENANCE_FIELDS)


def test_enforce_can_pass_allows_complete() -> None:
    enforce_can_pass(_complete())  # must not raise


def test_enforce_can_pass_rejects_incomplete() -> None:
    with pytest.raises(ProvenanceError, match="incomplete provenance"):
        enforce_can_pass(_complete(decision=None))
