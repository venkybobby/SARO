"""
EVF Sprint 2 tests — FR-EVF-10 (QCO Registry) + FR-EVF-20/21 (Publication Audit).

All tests use in-memory SQLite — no live DB required.

Covers:
  QCORegistry
    - Draft created only when gate is locked
    - Reference number format: SARO-QCO-{FW}-{YYYY}-{SEQ:03d}
    - Sequential reference numbers within same framework+year
    - Draft fields editable; published fields immutable (QCOImmutableError)
    - Publish sets issue_date, expiry_date, published_at, record_hash, prev_hash
    - expiry_date > issue_date + 365 days rejected (422)
    - Hash chain: second published QCO prev_hash == first record_hash
    - Renewal creates new draft referencing original; sets superseded_by_qco_id
    - active_only filter returns only non-expired, non-superseded published QCOs

  QCOPublicationEvent
    - Event written with all 5 required fields (AC-21a)
    - Hash chain: second event prev_hash == first event_hash
    - Tampered prev_hash breaks verify_chain
    - Idempotency key deduplicates retries
    - Invalid QCO reference rejected (422)
    - Invalid distribution_channel rejected at schema validation

  Integration
    - publish_qco emits a publication event in the same transaction
    - verify_publication_chain returns valid:True for clean chain
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── SQLite setup (must come before model imports) ──────────────────────────────
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

from database import Base
from models import (
    QCORegistry, QCOPublicationEvent,
)
Base.metadata.create_all(engine)

from services.evf_engagement_service import create_engagement
from services.evf_gate_service import update_gate, lock_gate
from services.evf_qco_service import (
    QCOImmutableError,
    create_qco_draft,
    get_qco_by_ref,
    list_qcos,
    publish_qco,
    renew_qco,
    update_qco_draft,
    MAX_VALIDITY_DAYS,
)
from services.evf_publication_service import (
    record_publication_event,
    list_publication_events,
    verify_publication_chain,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

ACTOR = uuid.uuid4()

_FULL_GATE_PATCH = {
    "coi_declared_approved": True, "coi_evidence_ref": "COI-001",
    "sow_executed": True, "sow_evidence_ref": "SOW-001",
    "evidence_package_delivered": True, "evidence_package_ref": "EP-001",
    "product_demo_completed": True, "product_demo_ref": "DEMO-001",
    "draft_qco_received": True, "draft_qco_ref": "DQCO-001",
    "saro_legal_review_completed": True, "legal_signoff_ref": "LEGAL-001",
    "qco_approved_ref_assigned": True, "qco_ref": "SARO-QCO-EU_AI_ACT-2026-001",
}


def _db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _session():
    return next(_db())


def _locked_engagement(db, framework: str = "EU_AI_ACT"):
    """Create an engagement whose gate is fully locked — prerequisite for QCO creation."""
    eng = create_engagement(
        db, sme_firm_name="Test Legal LLP", framework=framework,
        created_by_user_id=ACTOR,
    )
    update_gate(db, eng.id, updates=_FULL_GATE_PATCH)
    lock_gate(db, eng.id, locked_by_user_id=ACTOR)
    return eng


def _draft_qco(db, engagement=None, framework: str = "EU_AI_ACT"):
    if engagement is None:
        engagement = _locked_engagement(db, framework)
    return create_qco_draft(
        db,
        engagement_id=engagement.id,
        framework_covered=framework,
        saro_version_assessed="8.0.0",
        sme_firm="Acme Legal LLP",
        sme_credential="CIPP/E",
        scope_boundary_summary="Arts. 9, 13, 17 evidence support only",
        document_url=None,
        document_sha256=None,
        created_by_user_id=ACTOR,
    )


def _published_qco(db, engagement=None, framework: str = "EU_AI_ACT"):
    qco = _draft_qco(db, engagement, framework)
    return publish_qco(db, qco.id, published_by_user_id=ACTOR)


# ── FR-EVF-10: QCO Registry Tests ─────────────────────────────────────────────

class TestQCOGateEnforcement:
    def test_draft_requires_locked_gate(self):
        import fastapi
        db = _session()
        eng = create_engagement(
            db, sme_firm_name="Ungated LLP", framework="EU_AI_ACT",
            created_by_user_id=ACTOR,
        )
        # Gate NOT locked
        try:
            create_qco_draft(
                db, engagement_id=eng.id, framework_covered="EU_AI_ACT",
                saro_version_assessed="8.0.0", sme_firm="Acme", created_by_user_id=ACTOR,
                sme_credential=None, scope_boundary_summary=None,
                document_url=None, document_sha256=None,
            )
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 422
            assert "gate" in exc.detail.lower()
        db.close()

    def test_draft_allowed_with_locked_gate(self):
        db = _session()
        eng = _locked_engagement(db)
        qco = _draft_qco(db, eng)
        assert qco.id is not None
        assert qco.published is False
        db.close()


class TestQCOReferenceNumber:
    def test_reference_number_format(self):
        import re
        from datetime import datetime, timezone
        db = _session()
        eng = _locked_engagement(db, "NIST_AI_RMF")
        qco = _draft_qco(db, eng, "NIST_AI_RMF")
        year = datetime.now(timezone.utc).year
        pattern = rf"^SARO-QCO-NIST_AI_RMF-{year}-\d{{3}}$"
        assert re.match(pattern, qco.qco_reference_number), qco.qco_reference_number
        db.close()

    def test_sequential_numbers_same_framework(self):
        db = _session()
        eng1 = _locked_engagement(db, "AIGP")
        eng2 = _locked_engagement(db, "AIGP")
        q1 = _draft_qco(db, eng1, "AIGP")
        q2 = _draft_qco(db, eng2, "AIGP")
        seq1 = int(q1.qco_reference_number.split("-")[-1])
        seq2 = int(q2.qco_reference_number.split("-")[-1])
        assert seq2 == seq1 + 1
        db.close()

    def test_different_frameworks_independent_sequences(self):
        db = _session()
        eng_eu = _locked_engagement(db, "EU_AI_ACT")
        eng_iso = _locked_engagement(db, "ISO_42001")
        q_eu = _draft_qco(db, eng_eu, "EU_AI_ACT")
        q_iso = _draft_qco(db, eng_iso, "ISO_42001")
        assert "EU_AI_ACT" in q_eu.qco_reference_number
        assert "ISO_42001" in q_iso.qco_reference_number
        db.close()

    def test_get_by_ref(self):
        db = _session()
        qco = _draft_qco(db)
        fetched = get_qco_by_ref(db, qco.qco_reference_number)
        assert fetched.id == qco.id
        db.close()


class TestQCOImmutability:
    def test_draft_fields_editable(self):
        db = _session()
        qco = _draft_qco(db)
        updated = update_qco_draft(db, qco.id, updates={"sme_firm": "New Legal LLP"})
        assert updated.sme_firm == "New Legal LLP"
        db.close()

    def test_published_qco_rejects_patch(self):
        db = _session()
        qco = _published_qco(db)
        try:
            update_qco_draft(db, qco.id, updates={"sme_firm": "Should Fail"})
            assert False, "Expected QCOImmutableError"
        except QCOImmutableError as exc:
            assert exc.status_code == 409
        db.close()

    def test_published_qco_rejects_second_publish(self):
        db = _session()
        qco = _published_qco(db)
        try:
            publish_qco(db, qco.id, published_by_user_id=ACTOR)
            assert False, "Expected QCOImmutableError"
        except QCOImmutableError as exc:
            assert exc.status_code == 409
        db.close()


class TestQCOPublish:
    def test_publish_sets_required_fields(self):
        db = _session()
        qco = _published_qco(db)
        assert qco.published is True
        assert qco.published_at is not None
        assert qco.issue_date is not None
        assert qco.expiry_date is not None
        assert qco.record_hash is not None
        db.close()

    def test_default_expiry_is_365_days(self):
        db = _session()
        qco = _published_qco(db)
        delta = (qco.expiry_date - qco.issue_date).days
        assert delta == MAX_VALIDITY_DAYS
        db.close()

    def test_custom_expiry_accepted(self):
        db = _session()
        qco = _draft_qco(db)
        issue = date.today()
        expiry = issue + timedelta(days=180)
        published = publish_qco(db, qco.id, published_by_user_id=ACTOR,
                                issue_date=issue, expiry_date=expiry)
        assert (published.expiry_date - published.issue_date).days == 180
        db.close()

    def test_expiry_over_365_rejected(self):
        import fastapi
        db = _session()
        qco = _draft_qco(db)
        issue = date.today()
        expiry = issue + timedelta(days=366)
        try:
            publish_qco(db, qco.id, published_by_user_id=ACTOR,
                        issue_date=issue, expiry_date=expiry)
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 422
            assert "365" in exc.detail or "maximum" in exc.detail.lower()
        db.close()


class TestQCOHashChain:
    def test_first_published_prev_hash_is_none(self):
        db = _session()
        # Clear any QCOs written by earlier tests so this is truly the first publish
        db.query(QCOPublicationEvent).delete()
        db.query(QCORegistry).delete()
        db.commit()
        qco = _published_qco(db)
        assert qco.prev_hash is None
        assert qco.record_hash is not None
        db.close()

    def test_second_published_prev_hash_equals_first_record_hash(self):
        db = _session()
        q1 = _published_qco(db, framework="EU_AI_ACT")
        eng2 = _locked_engagement(db, "NIST_AI_RMF")
        q2 = _published_qco(db, eng2, framework="NIST_AI_RMF")
        assert q2.prev_hash == q1.record_hash
        db.close()

    def test_record_hash_is_deterministic(self):
        from services.evf_qco_service import _compute_record_hash
        db = _session()
        qco = _published_qco(db)
        recomputed = _compute_record_hash(qco, qco.prev_hash)
        assert recomputed == qco.record_hash
        db.close()


class TestQCORenewal:
    def test_renewal_creates_new_draft(self):
        db = _session()
        original = _published_qco(db)
        renewal = renew_qco(db, original.id, created_by_user_id=ACTOR)
        assert renewal.id != original.id
        assert renewal.published is False
        assert renewal.renews_qco_id == original.id
        db.close()

    def test_original_marked_superseded(self):
        db = _session()
        original = _published_qco(db)
        renewal = renew_qco(db, original.id, created_by_user_id=ACTOR)
        db.refresh(original)
        assert original.superseded_by_qco_id == renewal.id
        db.close()

    def test_renewal_of_draft_rejected(self):
        import fastapi
        db = _session()
        qco = _draft_qco(db)
        try:
            renew_qco(db, qco.id, created_by_user_id=ACTOR)
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 422
        db.close()


class TestQCOListActiveOnly:
    def test_active_only_excludes_unpublished(self):
        db = _session()
        _draft_qco(db)
        _published_qco(db)
        active = list_qcos(db, active_only=True)
        assert all(q.published for q in active)
        db.close()

    def test_active_only_excludes_superseded(self):
        db = _session()
        original = _published_qco(db)
        renew_qco(db, original.id, created_by_user_id=ACTOR)
        db.refresh(original)
        active = list_qcos(db, active_only=True)
        active_ids = {q.id for q in active}
        assert original.id not in active_ids
        db.close()


# ── FR-EVF-20/21: Publication Audit Tests ─────────────────────────────────────

class TestPublicationEvent:
    def _make_event(self, db, qco_ref=None, channel="API"):
        if qco_ref is None:
            qco = _published_qco(db)
            qco_ref = qco.qco_reference_number
        return record_publication_event(
            db,
            qco_reference_number=qco_ref,
            artefact_identifier="report:test-001",
            publisher_user_id=ACTOR,
            distribution_channel=channel,
        )

    def test_event_has_all_5_required_fields(self):
        """AC-21a: timestamp, artefact_identifier, qco_reference_number,
        publisher_user_id, distribution_channel must all be populated."""
        db = _session()
        event = self._make_event(db)
        assert event.timestamp is not None
        assert event.artefact_identifier == "report:test-001"
        assert event.qco_reference_number is not None
        assert event.publisher_user_id == ACTOR
        assert event.distribution_channel == "API"
        db.close()

    def test_event_has_hash(self):
        db = _session()
        event = self._make_event(db)
        assert event.event_hash is not None
        assert len(event.event_hash) == 64  # SHA-256 hex digest
        db.close()

    def test_invalid_qco_ref_rejected(self):
        import fastapi
        db = _session()
        try:
            record_publication_event(
                db, qco_reference_number="SARO-QCO-FAKE-0000-999",
                artefact_identifier="report:x", publisher_user_id=ACTOR,
                distribution_channel="API",
            )
            assert False, "Expected HTTPException"
        except fastapi.HTTPException as exc:
            assert exc.status_code == 422
        db.close()

    def test_idempotency_key_deduplicates(self):
        db = _session()
        qco = _published_qco(db)
        key = str(uuid.uuid4())
        e1 = record_publication_event(
            db, qco_reference_number=qco.qco_reference_number,
            artefact_identifier="report:001", publisher_user_id=ACTOR,
            distribution_channel="API", idempotency_key=key,
        )
        e2 = record_publication_event(
            db, qco_reference_number=qco.qco_reference_number,
            artefact_identifier="report:001-retry", publisher_user_id=ACTOR,
            distribution_channel="DASHBOARD", idempotency_key=key,
        )
        assert e1.id == e2.id  # same event returned
        db.close()

    def test_filter_by_channel(self):
        db = _session()
        qco = _published_qco(db)
        ref = qco.qco_reference_number
        record_publication_event(db, qco_reference_number=ref,
            artefact_identifier="a1", publisher_user_id=ACTOR, distribution_channel="API")
        record_publication_event(db, qco_reference_number=ref,
            artefact_identifier="a2", publisher_user_id=ACTOR, distribution_channel="REPORT_PDF")
        pdf_events = list_publication_events(db, distribution_channel="REPORT_PDF")
        assert all(e.distribution_channel == "REPORT_PDF" for e in pdf_events)
        db.close()


class TestPublicationHashChain:
    def test_first_event_prev_hash_is_none(self):
        db = _session()
        qco = _published_qco(db)
        # Clear any events that publish_qco already wrote
        db.query(QCOPublicationEvent).delete()
        db.commit()
        event = record_publication_event(
            db, qco_reference_number=qco.qco_reference_number,
            artefact_identifier="report:001", publisher_user_id=ACTOR,
            distribution_channel="API",
        )
        assert event.prev_hash is None
        db.close()

    def test_second_event_prev_hash_equals_first_event_hash(self):
        db = _session()
        qco = _published_qco(db)
        db.query(QCOPublicationEvent).delete()
        db.commit()
        ref = qco.qco_reference_number
        e1 = record_publication_event(db, qco_reference_number=ref,
            artefact_identifier="r1", publisher_user_id=ACTOR, distribution_channel="API")
        e2 = record_publication_event(db, qco_reference_number=ref,
            artefact_identifier="r2", publisher_user_id=ACTOR, distribution_channel="DASHBOARD")
        assert e2.prev_hash == e1.event_hash
        db.close()

    def test_verify_chain_valid_for_clean_chain(self):
        db = _session()
        qco = _published_qco(db)
        db.query(QCOPublicationEvent).delete()
        db.commit()
        ref = qco.qco_reference_number
        for i in range(3):
            record_publication_event(db, qco_reference_number=ref,
                artefact_identifier=f"report:{i}", publisher_user_id=ACTOR,
                distribution_channel="API")
        result = verify_publication_chain(db)
        assert result["valid"] is True
        assert result["events_checked"] == 3
        db.close()

    def test_verify_chain_detects_tampering(self):
        from sqlalchemy import text
        # Write session: create QCO, clear prior events, write e1 + e2
        db_write = _session()
        qco = _published_qco(db_write)
        db_write.query(QCOPublicationEvent).delete()
        db_write.commit()
        ref = qco.qco_reference_number
        e1 = record_publication_event(db_write, qco_reference_number=ref,
            artefact_identifier="r1", publisher_user_id=ACTOR, distribution_channel="API")
        record_publication_event(db_write, qco_reference_number=ref,
            artefact_identifier="r2", publisher_user_id=ACTOR, distribution_channel="DASHBOARD")
        # SQLite stores UUIDs without dashes; strip for raw SQL WHERE clause
        e1_id = str(e1.id).replace("-", "")
        db_write.close()

        # Tamper session: corrupt event_hash of first event via raw SQL
        db_tamper = _session()
        db_tamper.execute(
            text("UPDATE evf_publication_events SET event_hash = :h WHERE id = :id"),
            {"h": "a" * 64, "id": e1_id},
        )
        db_tamper.commit()
        db_tamper.close()

        # Verify session: fresh session — no identity map pollution
        db_verify = _session()
        result = verify_publication_chain(db_verify)
        db_verify.close()

        assert result["valid"] is False
        assert result["break_at_event_id"] is not None

    def test_verify_chain_empty(self):
        db = _session()
        db.query(QCOPublicationEvent).delete()
        db.commit()
        result = verify_publication_chain(db)
        assert result["valid"] is True
        assert result["events_checked"] == 0
        db.close()


# ── Integration: publish_qco emits publication event ─────────────────────────

class TestPublishEmitsEvent:
    def test_publish_writes_publication_event(self):
        db = _session()
        db.query(QCOPublicationEvent).delete()
        db.commit()
        _published_qco(db)
        events = list_publication_events(db)
        assert len(events) == 1
        assert events[0].distribution_channel == "API"
        assert events[0].artefact_identifier.startswith("qco:")
        db.close()

    def test_publish_event_qco_ref_matches(self):
        db = _session()
        db.query(QCOPublicationEvent).delete()
        db.commit()
        qco = _published_qco(db)
        events = list_publication_events(db, qco_reference_number=qco.qco_reference_number)
        assert len(events) == 1
        assert events[0].qco_reference_number == qco.qco_reference_number
        db.close()
