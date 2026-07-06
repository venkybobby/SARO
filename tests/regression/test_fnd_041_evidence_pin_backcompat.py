"""FND-041 — RPV-002 pin must not break verification of pre-RPV-002 evidence records.

Reviewer blocker B1: adding the rule-pack pin to the hashed payload unconditionally
would change the canonical JSON for every record captured before RPV-002 (whose
stored content_hash was computed without those keys), triggering a false
"content_hash mismatch" tamper alarm across the whole historical chain — exactly
what AC-4 forbids. The fix folds the pin in ONLY when non-NULL.

This test pins a content_hash computed the LEGACY way (no pin keys) and asserts the
current verifier still accepts it, and that a NULL-pin record verifies clean.
"""

from __future__ import annotations

import sys
import uuid
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
from models import GRCEvidenceRecord  # noqa: E402
from grc import evidence as ev  # noqa: E402

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

# The 10 legacy payload fields (pre-RPV-002) — the pin fields must NOT appear here.
_LEGACY_FIELDS = (
    "output_id",
    "system_id",
    "model_version",
    "prompt",
    "inputs",
    "retrieved_context",
    "decision",
    "confidence",
    "consumer",
    "captured_at",
)


@pytest.mark.regression
def test_legacy_content_hash_still_verifies():
    """A content_hash computed the pre-RPV-002 way must still verify today."""
    import hashlib
    import json

    data = {f: None for f in _LEGACY_FIELDS}
    data["output_id"] = "legacy-1"
    data["decision"] = "APPROVED"
    # Legacy canonical form: exactly the 10 fields, no pin keys.
    legacy_payload = {f: data.get(f) for f in _LEGACY_FIELDS}
    legacy_canonical = json.dumps(
        legacy_payload, sort_keys=True, default=ev._json_default
    )
    legacy_hash = hashlib.sha256(legacy_canonical.encode("utf-8")).hexdigest()

    # The current code path must reproduce the SAME hash for a NULL-pin record.
    assert ev.compute_content_hash(data) == legacy_hash

    db = _Session()
    try:
        rec = GRCEvidenceRecord(
            tenant_id=uuid.uuid4(),
            seq=1,
            output_id="legacy-1",
            decision="APPROVED",
            rule_pack_version_id=None,
            rule_pack_content_hash=None,
            content_hash=legacy_hash,
            prev_chain_hash=ev.GENESIS,
            chain_hash=ev.compute_chain_hash(legacy_hash, ev.GENESIS),
        )
        db.add(rec)
        db.commit()
        result = ev.verify_chain([rec])
        assert result.valid is True, result.reason
    finally:
        db.close()
