"""FND-068 — RP-OBS-COMPLETE misses an EMPTY required field, not just a null one.

Surfaced by the STORY-378 confusion-matrix harness on its first run: recall on
OBS-REQUIRED-FIELDS-1 was 0 because the check tested ``is None``, but the
adapters emit ``model_id = ""`` (with availability MISSING) when a model cannot
be identified — e.g. an endpoint-deployed Vertex model. So the completeness
rule could never fire on the exact real-world case it exists for.

Red-first: this failed before the fix.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adapters.contract import (  # noqa: E402
    NormalizedInvocationRecord,
    SourceProvenance,
)
from rule_packs.observation.evaluate import evaluate_record  # noqa: E402
from rule_packs.observation.loader import load_pack  # noqa: E402

pytestmark = pytest.mark.regression

OBS = ROOT / "rule_packs" / "observation" / "rp_obs_complete" / "1.0.0" / "pack.yaml"


def _record(**over):
    base = dict(
        provenance=SourceProvenance(adapter_id="t", cursor="c"),
        tenant_id=uuid.uuid4(),
        request_id="r",
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        operation="Converse",
        region="us-east-1",
        timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
        input_token_count=1,
        output_token_count=1,
    )
    base.update(over)
    return NormalizedInvocationRecord(**base)


def _fired(record):
    return {f.rule_id for f in evaluate_record(record, load_pack(OBS))}


def test_empty_model_id_fires_required_fields():
    """The endpoint-deployed-Vertex case: model_id='' + availability MISSING."""
    rec = _record(
        model_id="",
        field_availability=NormalizedInvocationRecord.mark_missing("model_id"),
    )
    assert "OBS-REQUIRED-FIELDS-1" in _fired(rec), (
        "an empty required field must count as absent, not present"
    )


def test_empty_operation_fires_required_fields():
    rec = _record(operation="")
    assert "OBS-REQUIRED-FIELDS-1" in _fired(rec)


def test_null_field_still_fires_the_regression_did_not_break_it():
    """The original None case must keep working."""
    rec = _record(input_token_count=None, output_token_count=None)
    assert "OBS-TOKEN-COUNTS-1" in _fired(rec)


def test_zero_token_count_is_not_treated_as_absent():
    """0 is a real count, not an empty value — must NOT fire the token rule."""
    rec = _record(input_token_count=0, output_token_count=0)
    assert "OBS-TOKEN-COUNTS-1" not in _fired(rec)


def test_fully_populated_record_fires_nothing():
    assert _fired(_record()) == set()
