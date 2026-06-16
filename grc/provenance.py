"""STORY-306 — Provenance completeness gate.

Absence of evidence must never be read as conformance. An output whose
provenance record is incomplete resolves to ``EVIDENCE_GAP`` — never ``PASS``.
This is the structural guard against fabricated compliance status and is wired
as a hard precondition in the orchestrator (STORY-308), not an advisory warning.

The required-provenance field list is reused from STORY-305
(:data:`grc.evidence.REQUIRED_PROVENANCE_FIELDS`) so there is a single source of
truth for what "complete provenance" means.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from grc.evidence import REQUIRED_PROVENANCE_FIELDS

EVIDENCE_GAP = "EVIDENCE_GAP"


class ProvenanceError(ValueError):
    """Raised when code attempts to PASS an output with incomplete provenance."""


class ProvenanceResult(BaseModel):
    complete: bool
    missing: list[str]
    # The forced disposition when incomplete; None when the output is eligible.
    disposition: str | None = None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _as_mapping(record: Any) -> Mapping[str, Any]:
    if record is None:
        return {}
    if isinstance(record, Mapping):
        return record
    if hasattr(record, "model_dump"):
        return record.model_dump()
    return {f: getattr(record, f, None) for f in REQUIRED_PROVENANCE_FIELDS}


def missing_provenance_fields(record: Any) -> list[str]:
    """Required provenance fields that are absent on ``record``."""
    data = _as_mapping(record)
    return [f for f in REQUIRED_PROVENANCE_FIELDS if _is_missing(data.get(f))]


def is_provenance_complete(record: Any) -> bool:
    return len(missing_provenance_fields(record)) == 0


def evaluate_provenance(record: Any) -> ProvenanceResult:
    """Eligibility check: complete → eligible for any disposition; else GAP."""
    missing = missing_provenance_fields(record)
    if missing:
        return ProvenanceResult(
            complete=False, missing=missing, disposition=EVIDENCE_GAP
        )
    return ProvenanceResult(complete=True, missing=[], disposition=None)


def enforce_can_pass(record: Any) -> None:
    """Hard guard: raise if anything tries to PASS incomplete provenance.

    The orchestrator calls this before assigning a ``PASS`` disposition so a
    PASS on an output with incomplete provenance is impossible, not merely
    discouraged (STORY-306 AC + STORY-312 rule 1 service side).
    """
    missing = missing_provenance_fields(record)
    if missing:
        raise ProvenanceError(
            f"cannot PASS: incomplete provenance (missing: {', '.join(missing)})"
        )
