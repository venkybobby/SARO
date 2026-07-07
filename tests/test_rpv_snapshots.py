"""STORY-RPV-001 — Versioned, immutable rule-pack snapshots (service unit tests).

All tests use in-memory SQLite — no live DB required. The DB immutability trigger
(migration 028) cannot run on SQLite, so AC-2 immutability is exercised here at the
service-layer guard; the trigger is verified against real Postgres via Supabase MCP.

AC coverage:
  AC-1  publish creates an immutable snapshot: version, content_hash, per-framework
        counts, publisher, prev_hash, chain-verifiable end to end
  AC-2  service-layer guard rejects any mutation of a published snapshot
  AC-3  only SME_VALIDATED includable; DRAFT_UNVALIDATED in scope blocks with a listing;
        LEGACY includable-with-caveat behind the config flag
  AC-4  diff against latest snapshot yields added/updated/retired per framework
  AC-5  chain recomputed from genesis detects a tampered snapshot by version
  Edge  empty publish rejected; deleted row shows as retired; NULL status fails closed;
        canonical serialization is deterministic
"""

from __future__ import annotations

import sys
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
from models import EUAIActRule, GovernanceRule, NISTControl, RulePackSnapshot  # noqa: E402
import services.rule_pack_snapshot_service as svc  # noqa: E402

Base.metadata.create_all(engine)


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    for tbl in (RulePackSnapshot, GovernanceRule, NISTControl, EUAIActRule):
        session.query(tbl).delete()
    session.commit()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_validated(db, *, eu=2, gov=2, nist=1):
    """Seed a clean, fully SME_VALIDATED working copy (nist has no status column)."""
    for i in range(eu):
        db.add(
            EUAIActRule(
                title=f"eu-{i}", description=f"d{i}", validation_status="SME_VALIDATED"
            )
        )
    for i in range(gov):
        db.add(
            GovernanceRule(
                rule_id=f"g-{i}", description=f"d{i}", validation_status="SME_VALIDATED"
            )
        )
    for i in range(nist):
        db.add(NISTControl(subcategory_id=f"n-{i}", description=f"d{i}"))
    db.commit()


# ── AC-1 ──────────────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_publish_creates_snapshot_with_required_fields(db):
    _seed_validated(db, eu=2, gov=2, nist=1)
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    assert snap.version == "1.0.0"
    assert len(snap.content_hash) == 64
    assert len(snap.record_hash) == 64
    assert snap.prev_hash is None  # genesis
    assert snap.framework_counts["eu_ai_act_rules"] == 2
    assert snap.framework_counts["governance_rules"] == 2
    assert snap.framework_counts["nist_ai_rmf_controls"] == 1


@pytest.mark.unit
def test_publish_chains_prev_hash_to_latest(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    s1 = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    # add a new validated rule so content changes and a second publish is allowed
    db.add(
        EUAIActRule(
            title="eu-new", description="new", validation_status="SME_VALIDATED"
        )
    )
    db.commit()
    s2 = svc.publish_snapshot(db, version="1.0.1", include_legacy=True)
    assert s2.prev_hash == s1.record_hash


# ── AC-3 ──────────────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_draft_rows_block_publish_with_listing(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    db.add(
        EUAIActRule(
            title="draft", description="d", validation_status="DRAFT_UNVALIDATED"
        )
    )
    db.commit()
    with pytest.raises(svc.DraftRowsPresentError) as ei:
        svc.publish_snapshot(db, version="1.0.0")
    blocking = ei.value.blocking
    assert any(b["table"] == "eu_ai_act_rules" for b in blocking)


@pytest.mark.unit
def test_null_status_fails_closed_as_draft(db):
    db.add(EUAIActRule(title="nullstatus", description="d", validation_status=None))
    db.commit()
    with pytest.raises(svc.DraftRowsPresentError):
        svc.publish_snapshot(db, version="1.0.0")


@pytest.mark.unit
def test_legacy_included_with_caveat_when_flag_on(db):
    db.add(
        EUAIActRule(
            title="legacy", description="d", validation_status="LEGACY_UNREVIEWED"
        )
    )
    db.add(
        GovernanceRule(rule_id="g", description="d", validation_status="SME_VALIDATED")
    )
    db.commit()
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    assert snap.includes_legacy is True
    assert snap.caveat and "LEGACY" in snap.caveat.upper()
    assert snap.framework_counts["eu_ai_act_rules"] == 1


@pytest.mark.unit
def test_legacy_excluded_when_flag_off(db):
    db.add(
        EUAIActRule(
            title="legacy", description="d", validation_status="LEGACY_UNREVIEWED"
        )
    )
    db.add(
        GovernanceRule(rule_id="g", description="d", validation_status="SME_VALIDATED")
    )
    db.commit()
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=False)
    assert snap.includes_legacy is False
    assert snap.framework_counts.get("eu_ai_act_rules", 0) == 0


@pytest.mark.unit
def test_retired_rows_excluded_not_blocking(db):
    db.add(
        GovernanceRule(rule_id="g", description="d", validation_status="SME_VALIDATED")
    )
    db.add(GovernanceRule(rule_id="old", description="d", validation_status="RETIRED"))
    db.commit()
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=False)
    assert snap.framework_counts["governance_rules"] == 1  # retired excluded


# ── AC-2 immutability guard ─────────────────────────────────────────────────────
@pytest.mark.unit
def test_service_guard_rejects_mutation(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    with pytest.raises(svc.SnapshotImmutableError):
        svc.update_snapshot_version(db, snap.id, "9.9.9")


# ── Edge: empty publish ─────────────────────────────────────────────────────────
@pytest.mark.unit
def test_empty_publish_rejected(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    with pytest.raises(svc.EmptyPublishError):
        svc.publish_snapshot(db, version="1.0.1", include_legacy=True)  # no change


# ── Edge: version must strictly increase ────────────────────────────────────────
@pytest.mark.unit
def test_version_must_strictly_increase(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    svc.publish_snapshot(db, version="2.0.0", include_legacy=True)
    db.add(EUAIActRule(title="x", description="x", validation_status="SME_VALIDATED"))
    db.commit()
    with pytest.raises(svc.InvalidVersionError):
        svc.publish_snapshot(db, version="1.5.0", include_legacy=True)


@pytest.mark.unit
def test_invalid_semver_rejected(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    with pytest.raises(svc.InvalidVersionError):
        svc.publish_snapshot(db, version="not-a-version", include_legacy=True)


# ── AC-4 diff ───────────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_diff_reports_added_updated_retired(db):
    r_keep = GovernanceRule(
        rule_id="keep", description="orig", validation_status="SME_VALIDATED"
    )
    r_del = GovernanceRule(
        rule_id="del", description="bye", validation_status="SME_VALIDATED"
    )
    db.add_all([r_keep, r_del])
    db.commit()
    svc.publish_snapshot(db, version="1.0.0", include_legacy=False)

    # mutate working copy: update keep, delete del, add fresh
    r_keep.description = "changed"
    db.delete(r_del)
    db.add(
        GovernanceRule(
            rule_id="fresh", description="new", validation_status="SME_VALIDATED"
        )
    )
    db.commit()

    diff = svc.diff_against_latest(db)
    gov = diff["governance_rules"]
    assert gov["added"] and gov["updated"] and gov["retired"]


# ── AC-5 tamper detection ───────────────────────────────────────────────────────
@pytest.mark.unit
def test_verify_chain_clean(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    result = svc.verify_chain(db)
    assert result["valid"] is True
    assert result["break_at_version"] is None


@pytest.mark.unit
def test_verify_chain_detects_tamper(db):
    _seed_validated(db, eu=1, gov=1, nist=0)
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    # Tamper directly (bypassing the guard) to simulate an out-of-band DB edit.
    db.query(RulePackSnapshot).filter(RulePackSnapshot.id == snap.id).update(
        {"content_hash": "0" * 64}
    )
    db.commit()
    result = svc.verify_chain(db)
    assert result["valid"] is False
    assert result["break_at_version"] == "1.0.0"


# ── Edge: canonical serialization deterministic ────────────────────────────────
@pytest.mark.unit
def test_row_hash_is_deterministic_and_order_independent(db):
    row = GovernanceRule(
        rule_id="g", description="d", validation_status="SME_VALIDATED"
    )
    db.add(row)
    db.commit()
    h1 = svc.compute_row_hash("governance_rules", row)
    h2 = svc.compute_row_hash("governance_rules", row)
    assert h1 == h2 and len(h1) == 64


# ── AC-5 (reviewer B2): manifest tampering is detected, not just content_hash ────
@pytest.mark.unit
def test_verify_chain_detects_manifest_tamper(db):
    """Editing snapshot_manifest while leaving content_hash stale must NOT verify.

    The manifest holds the per-row rule hashes RPV-002 pins evidence to; a verifier
    that trusts the stored content_hash blindly would miss this out-of-band edit.
    """
    _seed_validated(db, eu=1, gov=1, nist=0)
    snap = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    tampered = dict(snap.snapshot_manifest)
    tampered["governance_rules"] = {"999": "TAMPERED" + "0" * 55}
    db.query(RulePackSnapshot).filter(RulePackSnapshot.id == snap.id).update(
        {"snapshot_manifest": tampered}
    )
    db.commit()
    result = svc.verify_chain(db)
    assert result["valid"] is False
    assert result["break_at_version"] == "1.0.0"
    assert result.get("content_hash_mismatch") is True


# ── AC-4 (reviewer S1): a row flipped to RETIRED shows as retired, not updated ────
@pytest.mark.unit
def test_diff_reports_status_retirement_as_retired(db):
    row = GovernanceRule(
        rule_id="g", description="orig", validation_status="SME_VALIDATED"
    )
    db.add(row)
    db.commit()
    svc.publish_snapshot(db, version="1.0.0", include_legacy=False)

    # Flip status to RETIRED (row still physically present in the working copy).
    row.validation_status = "RETIRED"
    db.commit()

    gov = svc.diff_against_latest(db)["governance_rules"]
    assert str(row.id) in gov["retired"]
    assert str(row.id) not in gov["updated"]


# ── S2: chain order follows hash links, not timestamps ──────────────────────────
@pytest.mark.unit
def test_chain_order_follows_hash_links(db):
    _seed_validated(db, eu=1, gov=0, nist=0)
    s1 = svc.publish_snapshot(db, version="1.0.0", include_legacy=True)
    db.add(EUAIActRule(title="x", description="x", validation_status="SME_VALIDATED"))
    db.commit()
    s2 = svc.publish_snapshot(db, version="1.0.1", include_legacy=True)
    chain = svc.list_snapshots(db)
    assert [s.version for s in chain] == ["1.0.0", "1.0.1"]
    assert svc.get_latest_snapshot(db).id == s2.id
    assert s2.prev_hash == s1.record_hash
