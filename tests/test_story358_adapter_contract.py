"""STORY-358 — the observation adapter contract.

The load-bearing test here is ``test_contract_has_no_content_bearing_field``:
it enforces INV-2 structurally rather than by review. If someone adds a
``prompt`` or ``response_text`` field to the normalized record, this fails —
which is the whole reason the contract exists as a typed object.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from adapters.bedrock.records import BEDROCK_ADAPTER_ID, Envelope  # noqa: E402
from adapters.contract import (  # noqa: E402
    CONTRACT_VERSION,
    FieldAvailability,
    NormalizedInvocationRecord,
    SourceProvenance,
    ToolInvocation,
    from_bedrock_envelope,
)

pytestmark = pytest.mark.unit

_TENANT = uuid.uuid4()


def _envelope(**over) -> Envelope:
    base = dict(
        request_id="req-1",
        region="us-east-1",
        operation="Converse",
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        timestamp=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        cursor="s3:key:L1",
        input_token_count=120,
        output_token_count=45,
    )
    base.update(over)
    return Envelope(**base)


def _record(**over) -> NormalizedInvocationRecord:
    return from_bedrock_envelope(
        _envelope(**over.pop("envelope", {})),
        tenant_id=_TENANT,
        adapter_id=BEDROCK_ADAPTER_ID,
        **over,
    )


# ── AC-5 / INV-2: no field can carry message content ────────────────────────

_CONTENT_BEARING = {
    "prompt",
    "raw_output",
    "input_body",
    "output_body",
    "content",
    "message",
    "messages",
    "text",
    "completion",
    "response_text",
    "tool_input",
    "tool_arguments",
    "tool_result",
    "body",
}


def test_contract_has_no_content_bearing_field():
    """INV-2 in the type system: adding a body field to the contract fails here."""
    fields = set(NormalizedInvocationRecord.model_fields)
    leaked = fields & _CONTENT_BEARING
    assert not leaked, (
        f"content-bearing field(s) {sorted(leaked)} added to the normalized record — "
        "the engine's input contract must stay body-free (INV-2)"
    )


def test_tool_invocation_carries_name_only():
    leaked = set(ToolInvocation.model_fields) & _CONTENT_BEARING
    assert not leaked, f"tool arguments/results must not be in the contract: {leaked}"


# ── AC-1: the contract's shape ──────────────────────────────────────────────


def test_record_declares_contract_version_and_provenance():
    rec = _record()
    assert rec.contract_version == CONTRACT_VERSION
    assert rec.provenance.adapter_id == BEDROCK_ADAPTER_ID
    assert rec.provenance.cursor == "s3:key:L1"


def test_record_is_immutable():
    rec = _record()
    with pytest.raises(ValidationError):
        rec.model_id = "tampered"  # type: ignore[misc]


def test_provenance_accepts_hash_and_pointer():
    p = SourceProvenance(
        adapter_id="x", cursor="c", source_uri="s3://b/k", record_hash="a" * 64
    )
    assert p.source_uri == "s3://b/k" and len(p.record_hash) == 64


# ── AC-2: Bedrock conforms to the contract ──────────────────────────────────


def test_bedrock_envelope_lifts_to_normalized_record():
    rec = _record()
    assert rec.request_id == "req-1"
    assert rec.model_id.startswith("anthropic.claude-3")
    assert rec.operation == "Converse"
    assert rec.input_token_count == 120
    assert rec.tenant_id == _TENANT
    # tenant_id comes from operator config, never the log
    assert "tenant" not in rec.provenance.model_dump_json().lower()


def test_tools_expose_offered_and_invoked_sets():
    rec = _record(
        tools=(
            ToolInvocation(name="search_kb", offered=True, invoked=True),
            ToolInvocation(name="delete_record", offered=True, invoked=False),
        )
    )
    assert rec.invoked_tools == ("search_kb",)
    assert set(rec.offered_tools) == {"search_kb", "delete_record"}


def test_truncation_is_carried_for_obs_complete():
    rec = _record(stop_reason="max_tokens", truncated=True)
    assert rec.truncated is True and rec.stop_reason == "max_tokens"


# ── AC-3 semantics: absent ≠ unavailable ────────────────────────────────────


def test_absent_token_counts_are_marked_missing_not_silently_none():
    rec = _record(envelope={"input_token_count": None, "output_token_count": None})
    assert rec.input_token_count is None
    assert rec.availability("input_token_count") is FieldAvailability.MISSING
    assert rec.availability("output_token_count") is FieldAvailability.MISSING


def test_present_fields_report_present_without_being_listed():
    rec = _record()
    assert rec.availability("input_token_count") is FieldAvailability.PRESENT
    assert "input_token_count" not in rec.field_availability


def test_mark_unavailable_helper_builds_structural_gaps():
    gaps = NormalizedInvocationRecord.mark_unavailable("region", "stop_reason")
    assert gaps == {
        "region": FieldAvailability.UNAVAILABLE,
        "stop_reason": FieldAvailability.UNAVAILABLE,
    }


def test_unavailable_and_missing_are_distinguishable():
    """The distinction is the point: a provider gap is not a data-quality gap."""
    assert FieldAvailability.UNAVAILABLE.value == "field_unavailable"
    assert FieldAvailability.MISSING.value != FieldAvailability.UNAVAILABLE.value
