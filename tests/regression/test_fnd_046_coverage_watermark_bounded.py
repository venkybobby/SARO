"""FND-046 — observation checkpoint watermark must be a bounded opaque token (INV-2).

Security review of STORY-COV-001: CheckpointIn.watermark_position (and system_id/
adapter_id) had only min_length=1 — no max_length/pattern — so a caller could smuggle
free-text/PII into the coverage evidence store, defeating the story's core INV-2 property
(checkpoints carry positions + timestamps ONLY, never observed content).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from routers.observation_coverage import CheckpointIn  # noqa: E402

_TS = datetime(2026, 7, 7, tzinfo=timezone.utc)


@pytest.mark.regression
def test_watermark_rejects_freetext_and_overlong():
    # Free-text with spaces (a sentence / PII note) is rejected.
    with pytest.raises(ValidationError):
        CheckpointIn(system_id="s", adapter_id="a",
                     watermark_position="SSN 123-45-6789 patient note", watermark_timestamp=_TS)
    # Over-length (payload smuggling) is rejected.
    with pytest.raises(ValidationError):
        CheckpointIn(system_id="s", adapter_id="a",
                     watermark_position="x" * 500, watermark_timestamp=_TS)
    # A legitimate opaque token is accepted.
    ok = CheckpointIn(system_id="sys-1", adapter_id="bedrock",
                      watermark_position="seq-000123:offset=456", watermark_timestamp=_TS)
    assert ok.watermark_position == "seq-000123:offset=456"
