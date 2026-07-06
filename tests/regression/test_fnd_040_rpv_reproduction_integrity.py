"""FND-040 — RPV-002 reproduce_criteria must cross-check snapshot_content vs manifest.

Reviewer blocker B2: snapshot_content (the frozen rows an examiner actually reads)
is NOT covered by the snapshot content_hash chain. Without a read-time cross-check,
an out-of-band edit to snapshot_content is returned by reproduce_criteria while
verify_chain still reports valid — the FND-039 bug class, one layer deeper.

This test tampers snapshot_content directly and asserts reproduction flags it.
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
def test_tampered_snapshot_content_flagged_by_reproduction():
    db = _Session()
    try:
        db.add(
            EUAIActRule(
                title="clean", description="d", validation_status="SME_VALIDATED"
            )
        )
        db.add(
            GovernanceRule(
                rule_id="g", description="d", validation_status="SME_VALIDATED"
            )
        )
        db.commit()
        snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)

        repro = svc.reproduce_criteria(db, "1.0.0")
        assert repro["content_integrity"] is True
        assert repro["reproduction_available"] is True

        # Out-of-band edit to the reproduced content (not covered by content_hash).
        tampered = dict(snap.snapshot_content)
        tampered["eu_ai_act_rules"] = {
            "1": {"__table__": "eu_ai_act_rules", "__id__": "1", "title": "INJECTED"}
        }
        db.query(RulePackSnapshot).filter(RulePackSnapshot.id == snap.id).update(
            {"snapshot_content": tampered}
        )
        db.commit()

        repro = svc.reproduce_criteria(db, "1.0.0")
        assert repro["content_integrity"] is False
        assert repro["reproduction_available"] is False
        assert "integrity" in (repro["limitation"] or "").lower()
    finally:
        db.close()
