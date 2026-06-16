"""STORY-328 — Audit-result JSON contract + validation.

The audit output is the boundary artifact everything else relies on. This
module integrates ``ai_grc_audit_result.schema.json`` as the validation
contract for all audit outputs and exposes a single validation entry point.

The schema is the **single source of truth** for the enums (disposition,
risk band, evidence status, gate recommendation, verification status) and for
the three structural policy rules, which are enforced *in the schema* so they
hold for any producer:

1. ``PASS`` ⇒ evidence ``LINKED``.
2. ``CONDITIONAL`` / ``FAIL`` ⇒ a non-empty ``remediation``.
3. Any Critical ``FAIL`` ⇒ top-level ``gate_recommendation == NO_GO``.

Downstream code must import the enum tuples from here rather than redefining
them, so a schema change propagates everywhere.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).parent / "schema" / "ai_grc_audit_result.schema.json"


class ContractError(ValueError):
    """Raised when an audit-result instance does not conform to the contract."""


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    """Return the parsed JSON Schema document."""
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)  # fail fast on a bad schema
    return Draft202012Validator(schema)


def _enum(*path: str) -> tuple[str, ...]:
    """Pull an enum tuple out of the schema so it stays the single source."""
    node: Any = load_schema()
    for key in path:
        node = node[key]
    return tuple(node["enum"])


# Enum tuples sourced from the schema — import these, never redefine.
DISPOSITIONS = _enum("$defs", "disposition")
RISK_BANDS = _enum("$defs", "risk_band")
EVIDENCE_STATUSES = _enum("$defs", "evidence_status")
GATE_RECOMMENDATIONS = _enum("$defs", "gate_recommendation")
VERIFICATION_STATUSES = _enum("$defs", "verification_status")

SCHEMA_VERSION = "ai-grc-audit-result-1.0.0"


def validate_audit_result(instance: dict[str, Any]) -> dict[str, Any]:
    """Validate ``instance`` against the contract; return it unchanged if valid.

    Raises :class:`ContractError` listing every violation if not. This is the
    edge guard the orchestrator (STORY-308) calls before emitting a result.
    """
    errors = sorted(_validator().iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise ContractError(f"audit result violates contract: {detail}")
    return instance


def is_valid_audit_result(instance: dict[str, Any]) -> bool:
    """Boolean convenience wrapper around :func:`validate_audit_result`."""
    return _validator().is_valid(instance)
