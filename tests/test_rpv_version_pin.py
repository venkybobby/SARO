"""STORY-RPV-002 — evidence pins rule-pack version (service + evidence unit tests).

In-memory SQLite. Covers:
  AC-1  capture_evidence pins version+hash into the record, inside its content hash
        (tampering the pin breaks chain verification)
  AC-2  resolve_pinned_version: PERMISSIVE pins latest published / None when unpublished;
        STRICT refuses on no-version and on working-copy drift; broken chain refuses in both
  AC-3  reproduce_criteria returns the frozen content even after the working copy mutates
  AC-5  resolution derives from published snapshots, never the working copy
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON
import sqlalchemy.types as sa_types

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]

from database import Base  # noqa: E402
from models import EUAIActRule, GovernanceRule, GRCEvidenceRecord, RulePackSnapshot  # noqa: E402
import services.rule_pack_snapshot_service as svc  # noqa: E402
from grc.evidence import EvidenceCapture, capture_evidence, verify_chain  # noqa: E402

Base.metadata.create_all(engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000aa")


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    for tbl in (GRCEvidenceRecord, RulePackSnapshot, GovernanceRule, EUAIActRule):
        session.query(tbl).delete()
    session.commit()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _publish(db, *, title="orig"):
    db.add(EUAIActRule(title=title, description="d", validation_status="SME_VALIDATED"))
    db.add(
        GovernanceRule(rule_id="g", description="d", validation_status="SME_VALIDATED")
    )
    db.commit()
    return svc.publish_snapshot(db, version="1.0.0", include_legacy=True)


def _capture(db):
    return capture_evidence(
        db,
        tenant_id=_TENANT,
        capture=EvidenceCapture(
            output_id="out-1",
            model_version="m",
            prompt="p",
            decision="d",
            confidence=0.9,
            consumer="c",
        ),
    )


# ── AC-2 resolver ────────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_permissive_no_version_is_pre_versioning(db):
    v, h = svc.resolve_pinned_version(db, mode="PERMISSIVE")
    assert v is None and h is None


@pytest.mark.unit
def test_strict_no_version_refuses(db):
    with pytest.raises(svc.RulePackResolutionError):
        svc.resolve_pinned_version(db, mode="STRICT")


@pytest.mark.unit
def test_permissive_pins_latest_published(db):
    snap = _publish(db)
    v, h = svc.resolve_pinned_version(db, mode="PERMISSIVE")
    assert v == snap.version and h == snap.content_hash


@pytest.mark.unit
def test_strict_refuses_on_working_copy_drift(db):
    _publish(db)
    # working copy drifts: add a new validated rule not in the published snapshot
    db.add(EUAIActRule(title="new", description="d", validation_status="SME_VALIDATED"))
    db.commit()
    with pytest.raises(svc.RulePackResolutionError):
        svc.resolve_pinned_version(db, mode="STRICT")
    # PERMISSIVE still pins the published version (never the working copy)
    v, _ = svc.resolve_pinned_version(db, mode="PERMISSIVE")
    assert v == "1.0.0"


@pytest.mark.unit
def test_broken_chain_refuses_in_both_modes(db):
    snap = _publish(db)
    db.query(RulePackSnapshot).filter(RulePackSnapshot.id == snap.id).update(
        {"content_hash": "0" * 64}
    )
    db.commit()
    for mode in ("PERMISSIVE", "STRICT"):
        with pytest.raises(svc.RulePackIntegrityError):
            svc.resolve_pinned_version(db, mode=mode)


# ── AC-1 pin on evidence ─────────────────────────────────────────────────────────
@pytest.mark.unit
def test_capture_pins_version_and_hash(db):
    snap = _publish(db)
    rec = _capture(db)
    assert rec.rule_pack_version_id == snap.version
    assert rec.rule_pack_content_hash == snap.content_hash


@pytest.mark.unit
def test_capture_pre_versioning_when_unpublished(db):
    rec = _capture(db)
    assert rec.rule_pack_version_id is None
    assert rec.rule_pack_content_hash is None


@pytest.mark.unit
def test_pin_is_inside_content_hash(db):
    _publish(db)
    rec = _capture(db)
    # Clean chain verifies.
    assert verify_chain([rec]).valid is True
    # Tampering the pin (without recomputing the hash) breaks verification.
    rec.rule_pack_version_id = "9.9.9"
    assert verify_chain([rec]).valid is False


# ── AC-3 reproduction ────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_reproduce_returns_frozen_content_after_mutation(db):
    snap = _publish(db, title="ORIGINAL_TEXT")
    # mutate the working copy after publishing
    row = db.query(EUAIActRule).filter(EUAIActRule.title == "ORIGINAL_TEXT").first()
    row.title = "MUTATED_TEXT"
    db.commit()

    repro = svc.reproduce_criteria(db, snap.version)
    assert repro["reproduction_available"] is True
    eu_rows = repro["frameworks"]["eu_ai_act_rules"]
    assert any(r["title"] == "ORIGINAL_TEXT" for r in eu_rows)
    assert all(r["title"] != "MUTATED_TEXT" for r in eu_rows)
    assert repro["chain_verification"]["valid"] is True


@pytest.mark.unit
def test_reproduce_unknown_version_raises(db):
    with pytest.raises(svc.RulePackResolutionError):
        svc.reproduce_criteria(db, "9.9.9")
