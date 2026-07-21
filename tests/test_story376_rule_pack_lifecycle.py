"""STORY-376 — rule-pack draft→validate→publish workflow (delta on RPV-001/002).

The two load-bearing guarantees: publishing a new version does not disturb an
attestation issued under a prior version (INV-7), and the validation stage does
NOT fabricate an FP/FN pass it cannot yet compute.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import sqlalchemy.types as sa_types  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSON as PG_JSON  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine)
_orig = PG_UUID.__init__
PG_UUID.__init__ = lambda self, *a, **k: (k.pop("as_uuid", None), _orig(self, *a, **k))[1]  # type: ignore
PG_JSON.__init__ = lambda self, *a, **k: sa_types.Text.__init__(self)  # type: ignore

from database import Base  # noqa: E402
import models  # noqa: E402,F401
from models import RulePackSnapshot, TenantRulePackPin  # noqa: E402
import services.rule_pack_lifecycle as lifecycle  # noqa: E402

Base.metadata.create_all(engine)

pytestmark = pytest.mark.integration

GUIDE = ROOT / "docs" / "rule-pack-authoring.md"


@pytest.fixture
def db():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    s = TestingSessionLocal()
    yield s
    s.rollback()
    s.close()


def _publish(db, version, content_hash, prev=None):
    snap = RulePackSnapshot(
        version=version,
        content_hash=content_hash,
        prev_hash=prev,
        record_hash=f"rec-{version}",
        snapshot_manifest={},
        framework_counts={},
        includes_legacy=False,
    )
    db.add(snap)
    db.commit()
    return snap


# ── AC-3: tenant version pinning ────────────────────────────────────────────


def test_tenant_can_be_pinned_to_a_published_version(db, monkeypatch):
    monkeypatch.setattr("services.self_audit.record_privileged", lambda *a, **k: None)
    _publish(db, "1.0.0", "hashA")
    t = uuid.uuid4()

    result = lifecycle.pin_tenant_version(db, tenant_id=t, version="1.0.0", actor="op@x.test")
    assert result["version"] == "1.0.0"
    assert db.query(TenantRulePackPin).filter(TenantRulePackPin.tenant_id == t).count() == 1


def test_pinning_an_unpublished_version_is_refused(db):
    t = uuid.uuid4()
    with pytest.raises(lifecycle.PinTargetNotPublished):
        lifecycle.pin_tenant_version(db, tenant_id=t, version="9.9.9", actor="op@x.test")


def test_repinning_moves_the_tenant_without_deleting_the_old_version(db, monkeypatch):
    """Deprecation = re-pin. The old published snapshot must survive."""
    monkeypatch.setattr("services.self_audit.record_privileged", lambda *a, **k: None)
    _publish(db, "1.0.0", "hashA")
    _publish(db, "1.1.0", "hashB", prev="rec-1.0.0")
    t = uuid.uuid4()

    lifecycle.pin_tenant_version(db, tenant_id=t, version="1.0.0", actor="op@x.test")
    result = lifecycle.pin_tenant_version(db, tenant_id=t, version="1.1.0", actor="op@x.test")

    assert result["previous_version"] == "1.0.0"
    assert result["version"] == "1.1.0"
    # both published versions still exist — nothing was deleted
    assert db.query(RulePackSnapshot).count() == 2
    assert db.query(TenantRulePackPin).filter(TenantRulePackPin.tenant_id == t).count() == 1


def test_pin_change_is_audited_as_a_rule_pack_change(db):
    _publish(db, "1.0.0", "hashA")
    t = uuid.uuid4()
    calls = {}
    import services.self_audit as sa

    orig = sa.record_privileged
    try:
        sa.record_privileged = lambda _db, **kw: calls.update(kw)
        lifecycle.pin_tenant_version(db, tenant_id=t, version="1.0.0", actor="op@x.test")
    finally:
        sa.record_privileged = orig
    assert calls.get("action_class") == "RULE_PACK_CHANGE"
    assert calls["metadata"]["to_version"] == "1.0.0"


def test_unpinned_tenant_resolves_to_latest_published(db):
    _publish(db, "1.0.0", "hashA")
    _publish(db, "2.0.0", "hashB", prev="rec-1.0.0")
    assert lifecycle.resolve_tenant_version(db, uuid.uuid4()) == "2.0.0"


def test_pinned_tenant_resolves_to_its_pin_not_latest(db, monkeypatch):
    monkeypatch.setattr("services.self_audit.record_privileged", lambda *a, **k: None)
    _publish(db, "1.0.0", "hashA")
    _publish(db, "2.0.0", "hashB", prev="rec-1.0.0")
    t = uuid.uuid4()
    lifecycle.pin_tenant_version(db, tenant_id=t, version="1.0.0", actor="op@x.test")
    assert lifecycle.resolve_tenant_version(db, t) == "1.0.0"


# ── AC-2: attestation immutability across a republish ───────────────────────


def test_publishing_a_new_version_does_not_alter_a_prior_pinned_version(db, monkeypatch):
    """The core INV-7 guarantee an attestation depends on.

    A tenant pinned to 1.0.0 keeps evaluating against 1.0.0's exact content hash
    even after 2.0.0 is published — so an attestation issued under 1.0.0 remains
    reproducible.
    """
    monkeypatch.setattr("services.self_audit.record_privileged", lambda *a, **k: None)
    v1 = _publish(db, "1.0.0", "hash-v1")
    t = uuid.uuid4()
    lifecycle.pin_tenant_version(db, tenant_id=t, version="1.0.0", actor="op@x.test")

    _publish(db, "2.0.0", "hash-v2", prev="rec-1.0.0")

    # the pinned tenant still resolves to 1.0.0, and 1.0.0's content hash is intact
    assert lifecycle.resolve_tenant_version(db, t) == "1.0.0"
    db.refresh(v1)
    assert v1.content_hash == "hash-v1", "a prior version's content hash changed"


# ── AC-1: the validation stage is honest about the missing FP/FN bar ────────


def test_validation_defers_the_fp_fn_verdict_rather_than_fabricating_it():
    """377 (the bar) is human-gated and 378 (the harness) is not built."""
    assert lifecycle.BAR_PENDING == "bar_pending:STORY-377"
    # The verdict string names the dependency so no caller reads it as a pass.
    assert "STORY-377" in lifecycle.BAR_PENDING
    assert lifecycle.BAR_PENDING != "pass"


def test_lifecycle_states_are_ordered_draft_validation_published():
    assert lifecycle.STATES == ("draft", "validation", "published")


# ── AC-5: authoring guide ───────────────────────────────────────────────────


def test_authoring_guide_exists_and_states_immutability():
    doc = GUIDE.read_text(encoding="utf-8")
    assert "draft" in doc.lower() and "validate" in doc.lower() and "publish" in doc.lower()
    assert "immutable" in doc.lower()
    assert "INV-7" in doc


def test_authoring_guide_is_honest_about_the_pending_fp_fn_bar():
    doc = GUIDE.read_text(encoding="utf-8")
    assert "STORY-377" in doc, "the guide must not imply FP/FN validation works yet"


def test_authoring_guide_explains_deprecation_is_repinning_not_deletion():
    doc = GUIDE.read_text(encoding="utf-8").lower()
    assert "re-pin" in doc or "repin" in doc or "pin" in doc
    assert "never delete" in doc or "not deleted" in doc or "no delete" in doc
