"""FND-047 — concurrent coalescing emit must not poison the caller's session.

STORY-COV-002 wires emit_observation into the live audit path and deliberately coalesces
concurrent audits onto the SAME bucket watermark. record_checkpoint does an unlocked
SELECT-then-INSERT, so under concurrency two callers both pass the existence check and race
to INSERT; the loser's commit raises IntegrityError on ux_observation_checkpoints. Before the
fix, record_checkpoint neither caught nor rolled that back, leaving the shared request session
in PendingRollbackError state (poisoning downstream work on that session, e.g. the SAR-008
risk notification in scan_batch). It must instead roll back and return None — the idempotent
no-op the coalescing design already intends.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from database import Base  # noqa: E402
from models import ObservationCheckpoint  # noqa: E402
import services.observation_coverage_service as cov  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fc")
_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


@pytest.mark.regression
def test_checkpoint_race_returns_none_and_keeps_session_usable(monkeypatch):
    db = _Session()
    try:
        db.query(ObservationCheckpoint).delete()
        db.commit()

        # First writer wins the bucket.
        first = cov.record_checkpoint(
            db,
            tenant_id=_TENANT,
            system_id="s",
            adapter_id="a",
            watermark_position="obs:1",
            watermark_timestamp=_NOW,
        )
        assert first is not None

        # Simulate the race window: force the dedup SELECT to miss so the INSERT is attempted
        # against an already-present UNIQUE key — exactly what a concurrent commit produces.
        monkeypatch.setattr(cov, "_existing_checkpoint", lambda *a, **k: None)
        result = cov.record_checkpoint(
            db,
            tenant_id=_TENANT,
            system_id="s",
            adapter_id="a",
            watermark_position="obs:1",
            watermark_timestamp=_NOW,
        )

        assert result is None  # idempotent no-op — did NOT raise
        # The session was rolled back cleanly and remains usable; no duplicate row exists.
        assert db.query(ObservationCheckpoint).count() == 1
    finally:
        db.close()
