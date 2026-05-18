"""GAP-2: Notification system unit tests (TC-2.1 – TC-2.7 unit/integration layer)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock


from services.notification_service import (
    generate_threshold_notification,
    generate_drift_notification,
    get_unread_count,
)


def _make_db(existing_notif=None, count_val=0):
    """Return a mocked SQLAlchemy Session."""
    db = MagicMock()

    # Query chain for duplicate check
    query_mock = MagicMock()
    filter_mock = MagicMock()
    first_mock = MagicMock(return_value=existing_notif)

    query_mock.filter.return_value = filter_mock
    filter_mock.filter.return_value = filter_mock
    filter_mock.first.return_value = first_mock.return_value
    filter_mock.count.return_value = count_val

    db.query.return_value = query_mock
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    return db


# ── TC-2.1: Notification inserted when score < threshold ─────────────────────

class TestThresholdNotification:
    def test_inserts_notification_when_score_below_threshold(self):
        """TC-2.1 — exactly 1 DB insert; type=threshold_breach."""
        db = _make_db(existing_notif=None)
        generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=65, threshold=75, regulation="NIST RMF"
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        inserted = db.add.call_args[0][0]
        assert inserted.type == "threshold_breach"
        assert inserted.severity in ("critical", "high")
        assert "NIST RMF" in inserted.title

    def test_no_insert_when_score_at_or_above_threshold(self):
        """Score at threshold → no notification."""
        db = _make_db()
        result = generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=75, threshold=75, regulation="NIST RMF"
        )
        assert result is None
        db.add.assert_not_called()

    def test_no_insert_when_score_above_threshold(self):
        db = _make_db()
        result = generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=90, threshold=75, regulation="EU AI Act"
        )
        assert result is None
        db.add.assert_not_called()

    def test_severity_critical_when_very_low_score(self):
        """Score < 50% of threshold → severity=critical."""
        db = _make_db(existing_notif=None)
        generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=30, threshold=75, regulation="NIST RMF"
        )
        inserted = db.add.call_args[0][0]
        assert inserted.severity == "critical"

    def test_severity_high_when_moderately_low_score(self):
        """Score >= 50% of threshold → severity=high."""
        db = _make_db(existing_notif=None)
        generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=60, threshold=75, regulation="NIST RMF"
        )
        inserted = db.add.call_args[0][0]
        assert inserted.severity == "high"


# ── TC-2.2: Duplicate suppression ────────────────────────────────────────────

class TestDuplicateSuppression:
    def test_no_second_insert_if_unread_duplicate_exists(self):
        """TC-2.2 — existing unread notification of same type+regulation suppresses insert."""
        existing = MagicMock()
        existing.type = "threshold_breach"
        existing.read_at = None

        db = _make_db(existing_notif=existing)
        # Make the duplicate check return truthy
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing

        result = generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=50, threshold=75, regulation="NIST RMF"
        )
        assert result is None
        db.add.assert_not_called()

    def test_drift_notification_duplicate_suppressed(self):
        existing = MagicMock()
        existing.type = "drift_alert"
        existing.read_at = None

        db = _make_db(existing_notif=existing)
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = existing

        result = generate_drift_notification(
            db,
            tenant_id=uuid.uuid4(),
            framework="NIST AI RMF",
            current_version="1.0",
            latest_version="2.0",
            affected_packs=["nist_rmf_v1.0"],
        )
        assert result is None
        db.add.assert_not_called()


# ── TC-2.3: Unread count ──────────────────────────────────────────────────────

class TestUnreadCount:
    def test_returns_correct_unread_count(self):
        """TC-2.3 integration-style unit — get_unread_count queries correctly."""
        db = _make_db(count_val=3)
        tenant_id = uuid.uuid4()
        count = get_unread_count(db, tenant_id)
        assert count == 3

    def test_returns_zero_when_no_unread(self):
        db = _make_db(count_val=0)
        assert get_unread_count(db, uuid.uuid4()) == 0


# ── Drift notification ────────────────────────────────────────────────────────

class TestDriftNotification:
    def test_inserts_drift_notification(self):
        db = _make_db(existing_notif=None)
        generate_drift_notification(
            db,
            tenant_id=uuid.uuid4(),
            framework="EU AI Act",
            current_version="2024/1689",
            latest_version="2025/001",
            affected_packs=["eu_ai_act_v1.0"],
        )
        db.add.assert_called_once()
        inserted = db.add.call_args[0][0]
        assert inserted.type == "drift_alert"
        assert "EU AI Act" in inserted.title

    def test_notification_metadata_contains_regulation(self):
        db = _make_db(existing_notif=None)
        generate_threshold_notification(
            db, tenant_id=uuid.uuid4(), score=50, threshold=75, regulation="ISO 42001"
        )
        inserted = db.add.call_args[0][0]
        assert "ISO 42001" in inserted.metadata_json
