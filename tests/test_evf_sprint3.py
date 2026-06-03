"""
EVF Sprint 3 tests — FR-EVF-11 (Validation Status) + FR-EVF-13 (QCO Expiry).

All tests use in-memory SQLite — no live DB required.

Covers:
  Validation Status (FR-EVF-11)
    - Tier 3 returned when no engagement and no QCO
    - Tier 2 returned when engagement in active review state
    - Tier 2 (not Tier 1) when engagement in SHORTLISTED/COI_CLEARED
    - Tier 1 returned when active published non-expired QCO exists
    - Tier 1 label format matches FR-EVF-16 template
    - Expired QCO falls back to Tier 2 (not Tier 1)
    - get_all_framework_statuses covers all 4 frameworks

  QCO Expiry Scan (FR-EVF-13)
    - T-60 notification written and engagement → RENEWAL_TRIGGERED
    - T-30 notification written at 30-day mark
    - T-7  notification written at 7-day mark
    - EXPIRED + SALES_NOTIFY written for expired QCO
    - Idempotency: same scan day produces no duplicates
    - Non-expiring QCO produces no notifications
    - Scan returns correct counts
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── SQLite setup ───────────────────────────────────────────────────────────────
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
import models  # noqa: E402
from models import (
    QCOExpiryNotification,
    SMEEngagementState,
)
Base.metadata.create_all(engine)

from services.evf_engagement_service import create_engagement
from services.evf_gate_service import update_gate, lock_gate
from services.evf_qco_service import create_qco_draft, publish_qco
from services.evf_validation_status_service import (
    get_validation_status, get_all_framework_statuses,
    TIER_1, TIER_2, TIER_3,
)
from services.evf_expiry_service import (
    scan_qco_expiry,
    T_MINUS_60, T_MINUS_30, T_MINUS_7, EXPIRED, SALES_NOTIFY,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

ACTOR = uuid.uuid4()

_FULL_GATE = {
    "coi_declared_approved": True, "coi_evidence_ref": "COI-001",
    "sow_executed": True, "sow_evidence_ref": "SOW-001",
    "evidence_package_delivered": True, "evidence_package_ref": "EP-001",
    "product_demo_completed": True, "product_demo_ref": "DEMO-001",
    "draft_qco_received": True, "draft_qco_ref": "DQCO-001",
    "saro_legal_review_completed": True, "legal_signoff_ref": "LEGAL-001",
    "qco_approved_ref_assigned": True, "qco_ref": "SARO-QCO-EU_AI_ACT-2026-001",
}


def _session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _db():
    return next(_session())


def _locked_engagement(db, framework="EU_AI_ACT"):
    eng = create_engagement(db, sme_firm_name="Test LLP", framework=framework,
                            created_by_user_id=ACTOR)
    update_gate(db, eng.id, updates=_FULL_GATE)
    lock_gate(db, eng.id, locked_by_user_id=ACTOR)
    return eng


def _published_qco(db, framework="EU_AI_ACT", issue_date=None, expiry_date=None):
    eng = _locked_engagement(db, framework)
    qco = create_qco_draft(db, engagement_id=eng.id, framework_covered=framework,
                           saro_version_assessed="8.0.0", sme_firm="Acme Legal LLP",
                           sme_credential="CIPP/E", scope_boundary_summary="...",
                           document_url=None, document_sha256=None,
                           created_by_user_id=ACTOR)
    return publish_qco(db, qco.id, published_by_user_id=ACTOR,
                       issue_date=issue_date, expiry_date=expiry_date)


def _clear_evf_data(db):
    """Clear all EVF tables for test isolation."""
    db.query(QCOExpiryNotification).delete()
    db.query(models.QCOPublicationEvent).delete()
    db.query(models.QCORegistry).delete()
    db.query(models.ValidationGate).delete()
    db.query(models.SMEEngagementTransition).delete()
    db.query(models.SMEEngagement).delete()
    db.commit()


# ── FR-EVF-11: Validation Status Tests ────────────────────────────────────────

class TestTier3NoData:
    def test_no_engagement_no_qco_returns_tier3(self):
        db = _db()
        _clear_evf_data(db)
        result = get_validation_status(db, "EU_AI_ACT")
        assert result["tier"] == TIER_3
        assert result["qco_reference"] is None
        db.close()

    def test_tier3_label_is_internal_review_only(self):
        db = _db()
        _clear_evf_data(db)
        result = get_validation_status(db, "NIST_AI_RMF")
        assert "Internal Review Only" in result["label"]
        assert "Not for External Claim" in result["label"]
        db.close()

    def test_all_frameworks_covered(self):
        db = _db()
        _clear_evf_data(db)
        results = get_all_framework_statuses(db)
        assert len(results) == 4
        frameworks = {r["framework"] for r in results}
        assert frameworks == {"EU_AI_ACT", "NIST_AI_RMF", "AIGP", "ISO_42001"}
        db.close()


class TestTier2ActiveEngagement:
    def _make_engagement_in_state(self, db, state: str, framework="EU_AI_ACT"):
        from services.evf_engagement_service import transition_engagement
        eng = create_engagement(db, sme_firm_name="Active LLP",
                                framework=framework, created_by_user_id=ACTOR)
        # Advance through states to reach desired state
        state_chain = [
            "COI_CLEARED", "SOW_ISSUED", "REVIEW_IN_PROGRESS",
            "DRAFT_QCO_RECEIVED", "QCO_APPROVED",
        ]
        for s in state_chain:
            if eng.state == state:
                break
            transition_engagement(db, eng.id, to_state=s, actor_user_id=ACTOR)
            if s == state:
                break
        return eng

    def test_sow_issued_returns_tier2(self):
        db = _db()
        _clear_evf_data(db)
        self._make_engagement_in_state(db, "SOW_ISSUED")
        result = get_validation_status(db, "EU_AI_ACT")
        assert result["tier"] == TIER_2
        db.close()

    def test_review_in_progress_returns_tier2(self):
        db = _db()
        _clear_evf_data(db)
        self._make_engagement_in_state(db, "REVIEW_IN_PROGRESS")
        result = get_validation_status(db, "EU_AI_ACT")
        assert result["tier"] == TIER_2
        db.close()

    def test_tier2_label_contains_approved_text(self):
        db = _db()
        _clear_evf_data(db)
        self._make_engagement_in_state(db, "SOW_ISSUED")
        result = get_validation_status(db, "EU_AI_ACT")
        assert "undergoing independent review" in result["label"]
        assert "Claims will be published" in result["label"]
        db.close()

    def test_shortlisted_returns_tier3_not_tier2(self):
        """SHORTLISTED is not an active review state — must stay Tier 3."""
        db = _db()
        _clear_evf_data(db)
        create_engagement(db, sme_firm_name="Early LLP",
                          framework="AIGP", created_by_user_id=ACTOR)
        result = get_validation_status(db, "AIGP")
        assert result["tier"] == TIER_3
        db.close()


class TestTier1ActiveQCO:
    def test_active_published_qco_returns_tier1(self):
        db = _db()
        _clear_evf_data(db)
        _published_qco(db, "ISO_42001")
        result = get_validation_status(db, "ISO_42001")
        assert result["tier"] == TIER_1
        db.close()

    def test_tier1_label_contains_qco_ref(self):
        db = _db()
        _clear_evf_data(db)
        qco = _published_qco(db, "EU_AI_ACT")
        result = get_validation_status(db, "EU_AI_ACT")
        assert qco.qco_reference_number in result["label"]
        assert "Externally Reviewed" in result["label"]
        db.close()

    def test_tier1_label_contains_sme_firm(self):
        db = _db()
        _clear_evf_data(db)
        _published_qco(db, "EU_AI_ACT")
        result = get_validation_status(db, "EU_AI_ACT")
        assert "Acme Legal LLP" in result["label"]
        db.close()

    def test_tier1_returns_qco_reference(self):
        db = _db()
        _clear_evf_data(db)
        qco = _published_qco(db, "NIST_AI_RMF")
        result = get_validation_status(db, "NIST_AI_RMF")
        assert result["qco_reference"] == qco.qco_reference_number
        db.close()

    def test_tier1_returns_expires_in_days(self):
        db = _db()
        _clear_evf_data(db)
        _published_qco(db, "AIGP")
        result = get_validation_status(db, "AIGP")
        assert result["expires_in_days"] is not None
        assert 0 < result["expires_in_days"] <= 365
        db.close()


class TestExpiredQCOFallback:
    def test_expired_qco_returns_tier2_not_tier1(self):
        db = _db()
        _clear_evf_data(db)
        yesterday = date.today() - timedelta(days=1)
        _published_qco(db, "EU_AI_ACT",
                       issue_date=date.today() - timedelta(days=366),
                       expiry_date=yesterday)
        result = get_validation_status(db, "EU_AI_ACT")
        assert result["tier"] == TIER_2
        db.close()

    def test_expired_qco_note_in_result(self):
        db = _db()
        _clear_evf_data(db)
        yesterday = date.today() - timedelta(days=1)
        _published_qco(db, "EU_AI_ACT",
                       issue_date=date.today() - timedelta(days=366),
                       expiry_date=yesterday)
        result = get_validation_status(db, "EU_AI_ACT")
        assert "expired" in result.get("note", "").lower()
        db.close()


# ── FR-EVF-13: QCO Expiry Scan Tests ──────────────────────────────────────────

class TestExpiryScanNoAction:
    def test_no_qcos_nothing_happens(self):
        db = _db()
        _clear_evf_data(db)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result["scanned"] == 0
        assert result[T_MINUS_60] == 0
        db.close()

    def test_far_future_qco_no_notifications(self):
        db = _db()
        _clear_evf_data(db)
        future_expiry = date.today() + timedelta(days=200)
        _published_qco(db, "EU_AI_ACT", expiry_date=future_expiry)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result[T_MINUS_60] == 0
        assert result[T_MINUS_30] == 0
        assert result[T_MINUS_7] == 0
        assert result[EXPIRED] == 0
        db.close()


class TestExpiryScanT60:
    def test_t60_notification_written(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() + timedelta(days=60)
        _published_qco(db, "EU_AI_ACT", expiry_date=expiry)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result[T_MINUS_60] == 1
        db.close()

    def test_t60_triggers_renewal_on_engagement(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() + timedelta(days=60)
        # After publish_qco, engagement should be in PUBLISHED state
        _published_qco(db, "EU_AI_ACT", expiry_date=expiry)
        # Advance engagement to PUBLISHED state first
        from services.evf_engagement_service import transition_engagement
        eng = db.query(models.SMEEngagement).filter(
            models.SMEEngagement.framework == "EU_AI_ACT"
        ).first()
        if eng and eng.state != "PUBLISHED":
            # Advance to PUBLISHED via chain
            state_chain = ["COI_CLEARED", "SOW_ISSUED", "REVIEW_IN_PROGRESS",
                           "DRAFT_QCO_RECEIVED", "QCO_APPROVED", "PUBLISHED"]
            for s in state_chain:
                if eng.state == s:
                    break
                try:
                    transition_engagement(db, eng.id, to_state=s, actor_user_id=ACTOR)
                except Exception:
                    pass
        scan_qco_expiry(db, reference_date=date.today())
        db.refresh(eng)
        assert eng.state == SMEEngagementState.RENEWAL_TRIGGERED.value
        db.close()

    def test_t60_idempotent_same_day(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() + timedelta(days=60)
        _published_qco(db, "EU_AI_ACT", expiry_date=expiry)
        r1 = scan_qco_expiry(db, reference_date=date.today())
        r2 = scan_qco_expiry(db, reference_date=date.today())
        assert r1[T_MINUS_60] == 1
        assert r2[T_MINUS_60] == 0  # idempotent — not re-sent
        db.close()


class TestExpiryScanT30:
    def test_t30_notification_written(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() + timedelta(days=30)
        _published_qco(db, "NIST_AI_RMF", expiry_date=expiry)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result[T_MINUS_30] == 1
        db.close()

    def test_t30_not_written_for_t60_window(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() + timedelta(days=60)
        _published_qco(db, "NIST_AI_RMF", expiry_date=expiry)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result[T_MINUS_30] == 0
        db.close()


class TestExpiryScanT7:
    def test_t7_notification_written(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() + timedelta(days=7)
        _published_qco(db, "AIGP", expiry_date=expiry)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result[T_MINUS_7] == 1
        db.close()


class TestExpiryScanExpired:
    def test_expired_writes_expired_and_sales_notify(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() - timedelta(days=5)
        _published_qco(db, "ISO_42001",
                       issue_date=date.today() - timedelta(days=370),
                       expiry_date=expiry)
        result = scan_qco_expiry(db, reference_date=date.today())
        assert result[EXPIRED] == 1
        assert result[SALES_NOTIFY] == 1
        db.close()

    def test_expired_idempotent(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() - timedelta(days=5)
        _published_qco(db, "ISO_42001",
                       issue_date=date.today() - timedelta(days=370),
                       expiry_date=expiry)
        r1 = scan_qco_expiry(db, reference_date=date.today())
        r2 = scan_qco_expiry(db, reference_date=date.today())
        assert r1[EXPIRED] == 1
        assert r2[EXPIRED] == 0  # idempotent
        db.close()

    def test_expired_qco_now_tier2(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() - timedelta(days=1)
        _published_qco(db, "EU_AI_ACT",
                       issue_date=date.today() - timedelta(days=366),
                       expiry_date=expiry)
        scan_qco_expiry(db, reference_date=date.today())
        status = get_validation_status(db, "EU_AI_ACT")
        assert status["tier"] == TIER_2
        db.close()

    def test_expiry_notification_db_record(self):
        db = _db()
        _clear_evf_data(db)
        expiry = date.today() - timedelta(days=1)
        _published_qco(db, "EU_AI_ACT",
                       issue_date=date.today() - timedelta(days=366),
                       expiry_date=expiry)
        scan_qco_expiry(db, reference_date=date.today())
        notifications = db.query(QCOExpiryNotification).filter(
            QCOExpiryNotification.notification_type == EXPIRED
        ).all()
        assert len(notifications) == 1
        assert notifications[0].framework == "EU_AI_ACT"
        db.close()
