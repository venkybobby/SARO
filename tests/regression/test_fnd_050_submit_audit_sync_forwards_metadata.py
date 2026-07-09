"""FND-050 — submit_audit_sync silently dropped `metadata` instead of forwarding
it to the engine.

`services/audit_submission.py`'s `submit_audit_sync` has received `metadata` as a
parameter since STORY-406 (it uses it to build `ScanReport.report_json
["adapter_metadata"]`), but never passed it into `engine_obj.run_output_audit(...)`
— only `audit_id`/`raw_output`/`prompt`/`source_model` were forwarded. This meant
`run_output_audit` could never see envelope fields like `modelId`/`requestId`,
which is what kept STORY-411's model-allowlist rule (and any future envelope-only
evaluation) structurally blind even after the engine itself gained the capability
to evaluate them. Found during STORY-411's verify stage (independent reviewer).

Fix: `submit_audit_sync` now passes `metadata=metadata` into `run_output_audit`.
This test pins the forwarding itself — independent of the envelope-allowlist
feature — so a future refactor of `submit_audit_sync`'s call to `run_output_audit`
cannot silently drop `metadata` again without this test catching it.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from database import Base  # noqa: E402
from models import Audit, AuditMetadata, ScanReport  # noqa: E402

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fc")
_USER = uuid.UUID("00000000-0000-0000-0000-0000000000fd")


@pytest.mark.regression
def test_submit_audit_sync_forwards_metadata_to_run_output_audit():
    from services.audit_submission import submit_audit_sync

    captured_kwargs: dict = {}

    class _CapturingEngine:
        def __init__(self, db):
            pass

        def run_output_audit(self, **kw):
            captured_kwargs.update(kw)
            return SimpleNamespace(
                status="completed",
                confidence_score=0.5,
                mit_coverage=SimpleNamespace(score=0.0),
                fixed_delta=SimpleNamespace(delta=0.0),
                bayesian_scores=SimpleNamespace(overall=0.0),
                model_dump=lambda mode="json": {},
            )

    db = _Session()
    try:
        db.query(ScanReport).delete()
        db.query(AuditMetadata).delete()
        db.query(Audit).delete()
        db.commit()

        sentinel_metadata = {"modelId": "anthropic.claude-3-sonnet", "requestId": "r-1"}
        submit_audit_sync(
            db,
            tenant_id=_TENANT,
            user_id=_USER,
            prompt="p",
            raw_output="o",
            source_model="claude",
            metadata=sentinel_metadata,
            engine_factory=_CapturingEngine,
            persist_traces=lambda *a: None,
        )

        assert "metadata" in captured_kwargs, (
            "submit_audit_sync must forward metadata into run_output_audit — "
            "regression for the silent-drop bug (FND-050)"
        )
        assert captured_kwargs["metadata"] == sentinel_metadata
    finally:
        db.close()
