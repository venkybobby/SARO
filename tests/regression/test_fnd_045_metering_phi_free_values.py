"""FND-045 — usage-meter dimension VALUES must be bounded (PHI-free by construction).

Security review of STORY-MTR-001: _validate originally bounded dimension KEYS but not
VALUES, so a future caller could smuggle raw payload/PII into the dimensions JSONB via
a value (e.g. adapter_id="<raw client output>"). AC-1 requires PHI-freeness "by
construction, not by redaction" — values must be bounded scalars regardless of caller.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

import services.metering_service as m  # noqa: E402

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000f9")


@pytest.mark.regression
def test_metering_rejects_payload_in_dimension_values():
    # A long value (payload smuggling) is rejected.
    with pytest.raises(m.MeteringError):
        m._validate(m.EVALUATIONS_EXECUTED, {"adapter_id": "P" * 500})
    # A non-scalar value is rejected.
    with pytest.raises(m.MeteringError):
        m._validate(m.EVALUATIONS_EXECUTED, {"vertical": {"raw": "phi"}})
    # An enum-bounded key rejects an out-of-vocabulary value.
    with pytest.raises(m.MeteringError):
        m._validate(m.EVALUATIONS_EXECUTED, {"outcome": "LEAKED_CONTENT"})
    # A legitimate short, in-vocabulary set is accepted.
    m._validate(m.EVALUATIONS_EXECUTED, {"outcome": "GO", "gate_id": "gate2"})
