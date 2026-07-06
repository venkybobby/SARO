"""FND-039 — RPV-001 snapshot verify must re-derive content_hash from the manifest.

Regression pin for reviewer blocker B2: verify_chain originally trusted the stored
content_hash and only recomputed record_hash, so an out-of-band edit to
snapshot_manifest (the per-row rule hashes RPV-002 pins evidence to) that left
content_hash stale still returned valid:true — defeating AC-5 ("any tampered
snapshot is detected") under the exact out-of-band-DB-edit threat model.

This test tampers ONLY the manifest and asserts the verifier flags the break.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON  # noqa: E402
import sqlalchemy.types as sa_types  # noqa: E402

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]

from database import Base  # noqa: E402
from models import EUAIActRule, GovernanceRule, RulePackSnapshot  # noqa: E402
import services.rule_pack_snapshot_service as svc  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


@pytest.mark.regression
def test_manifest_tamper_breaks_verify():
    db = _Session()
    try:
        db.add(
            EUAIActRule(title="eu", description="d", validation_status="SME_VALIDATED")
        )
        db.add(
            GovernanceRule(
                rule_id="g", description="d", validation_status="SME_VALIDATED"
            )
        )
        db.commit()
        snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
        assert svc.verify_chain(db)["valid"] is True

        tampered = dict(snap.snapshot_manifest)
        tampered["governance_rules"] = {"42": "n0tarealrowhash" + "0" * 49}
        db.query(RulePackSnapshot).filter(RulePackSnapshot.id == snap.id).update(
            {"snapshot_manifest": tampered}
        )
        db.commit()

        result = svc.verify_chain(db)
        assert result["valid"] is False
        assert result["break_at_version"] == "1.0.0"
        assert result.get("content_hash_mismatch") is True
    finally:
        db.close()
