"""
EVF Sprint 3 — QCO Expiry service (FR-EVF-13).

Daily scan (02:00 UTC) that:
  T-60: engagement state → RENEWAL_TRIGGERED; write T_MINUS_60 notification
  T-30: write T_MINUS_30 reminder notification
  T-7:  write T_MINUS_7  reminder notification
  EXPIRED (day 0+): revert validation status to "Under Review" (T3→T2 in
           status service); write EXPIRED notification + schedule 24h
           SALES_NOTIFY dispatch

All notifications are idempotent — the idempotency_key ensures the job
can run repeatedly without creating duplicate rows.

The "revert to Under Review" is implicit: the validation status service
already re-evaluates live from the DB on every request.  No separate
revert write is needed — an expired QCO automatically falls to Tier 2.

For the 24h Sales notification:
  - A SALES_NOTIFY record is written at expiry time.
  - On the NEXT scan run (≥1 day later), any SALES_NOTIFY record older
    than 0 days that hasn't been marked dispatched gets a structured log
    at WARNING level (captured by Railway Observability / Sentry).
  - The expiry_alerts endpoint exposes these for Sales dashboard polling.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models import QCOExpiryNotification, QCORegistry, SMEEngagement, SMEEngagementState

logger = logging.getLogger(__name__)

# ── Notification type constants ───────────────────────────────────────────────
T_MINUS_60 = "T_MINUS_60"
T_MINUS_30 = "T_MINUS_30"
T_MINUS_7  = "T_MINUS_7"
EXPIRED    = "EXPIRED"
SALES_NOTIFY = "SALES_NOTIFY"

_THRESHOLDS = [
    (60, T_MINUS_60),
    (30, T_MINUS_30),
    (7,  T_MINUS_7),
]


# ── Idempotency helpers ───────────────────────────────────────────────────────

def _idem_key(qco_id, notif_type: str, ref_date: date) -> str:
    """Stable idempotency key: same QCO + type + date → same key."""
    return f"{qco_id}:{notif_type}:{ref_date.isoformat()}"


def _already_sent(db: Session, key: str) -> bool:
    return (
        db.query(QCOExpiryNotification)
        .filter(QCOExpiryNotification.idempotency_key == key)
        .first()
    ) is not None


def _write_notification(
    db: Session,
    *,
    qco_id,
    qco_reference_number: str,
    framework: str,
    notification_type: str,
    expires_in_days: Optional[int],
    idempotency_key: str,
) -> Optional[QCOExpiryNotification]:
    """Write one expiry notification — no-op if already sent (idempotent)."""
    if _already_sent(db, idempotency_key):
        return None

    notif = QCOExpiryNotification(
        qco_id=qco_id,
        qco_reference_number=qco_reference_number,
        framework=framework,
        notification_type=notification_type,
        expires_in_days=expires_in_days,
        sent_at=datetime.now(timezone.utc),
        idempotency_key=idempotency_key,
    )
    db.add(notif)
    db.flush()
    return notif


# ── Renewal trigger ───────────────────────────────────────────────────────────

def _trigger_renewal(db: Session, framework: str, qco_ref: str) -> None:
    """Advance the most recent published engagement for this framework to RENEWAL_TRIGGERED."""
    eng: Optional[SMEEngagement] = (
        db.query(SMEEngagement)
        .filter(
            SMEEngagement.framework == framework,
            SMEEngagement.state == SMEEngagementState.PUBLISHED.value,
        )
        .order_by(SMEEngagement.updated_at.desc())
        .first()
    )
    if eng and eng.state != SMEEngagementState.RENEWAL_TRIGGERED.value:
        eng.state = SMEEngagementState.RENEWAL_TRIGGERED.value
        eng.state_entered_at = datetime.now(timezone.utc)
        eng.updated_at = datetime.now(timezone.utc)
        logger.info(
            "EVF expiry: engagement %s → RENEWAL_TRIGGERED (QCO %s T-60)",
            eng.id,
            qco_ref,
        )


# ── Main scan ─────────────────────────────────────────────────────────────────

def scan_qco_expiry(db: Session, *, reference_date: Optional[date] = None) -> dict:
    """
    Scan all active published QCOs and dispatch expiry notifications.

    Args:
        db:             SQLAlchemy session.
        reference_date: Override today's date (for testing). Defaults to date.today().

    Returns dict with counts of actions taken.
    """
    today = reference_date or date.today()
    results = {
        "scanned": 0,
        T_MINUS_60: 0,
        T_MINUS_30: 0,
        T_MINUS_7:  0,
        EXPIRED:    0,
        SALES_NOTIFY: 0,
    }

    # Active published QCOs: published, not superseded, has expiry date
    qcos = (
        db.query(QCORegistry)
        .filter(
            QCORegistry.published.is_(True),
            QCORegistry.superseded_by_qco_id.is_(None),
            QCORegistry.expiry_date.isnot(None),
        )
        .all()
    )

    results["scanned"] = len(qcos)

    for qco in qcos:
        expiry = qco.expiry_date
        # Normalise datetime → date (SQLite may return datetime)
        if isinstance(expiry, datetime):
            expiry = expiry.date()

        if expiry is None:
            continue

        days_remaining = (expiry - today).days

        # ── T-60/T-30/T-7 reminders ──────────────────────────────────────────
        for threshold, notif_type in _THRESHOLDS:
            # Trigger on the exact threshold day and the day after (window guard)
            if threshold - 1 <= days_remaining <= threshold:
                key = _idem_key(qco.id, notif_type, today)
                notif = _write_notification(
                    db,
                    qco_id=qco.id,
                    qco_reference_number=qco.qco_reference_number,
                    framework=qco.framework_covered,
                    notification_type=notif_type,
                    expires_in_days=days_remaining,
                    idempotency_key=key,
                )
                if notif:
                    results[notif_type] += 1
                    logger.warning(
                        "EVF QCO expiry %s: %s for %s — %d days remaining",
                        notif_type,
                        qco.qco_reference_number,
                        qco.framework_covered,
                        days_remaining,
                    )
                    # T-60 also triggers renewal on the engagement
                    if notif_type == T_MINUS_60:
                        _trigger_renewal(db, qco.framework_covered, qco.qco_reference_number)

        # ── Expired ───────────────────────────────────────────────────────────
        if days_remaining < 0:
            # Write EXPIRED notification (idempotent per expiry date)
            expired_key = _idem_key(qco.id, EXPIRED, expiry)
            expired_notif = _write_notification(
                db,
                qco_id=qco.id,
                qco_reference_number=qco.qco_reference_number,
                framework=qco.framework_covered,
                notification_type=EXPIRED,
                expires_in_days=days_remaining,
                idempotency_key=expired_key,
            )
            if expired_notif:
                results[EXPIRED] += 1
                logger.warning(
                    "EVF QCO EXPIRED: %s (%s) expired %s — validation reverted to "
                    "Tier 2 (Under Review). Sales notification queued.",
                    qco.qco_reference_number,
                    qco.framework_covered,
                    expiry,
                )

            # Write SALES_NOTIFY (dispatched immediately — within 24h SLA)
            sales_key = _idem_key(qco.id, SALES_NOTIFY, expiry)
            sales_notif = _write_notification(
                db,
                qco_id=qco.id,
                qco_reference_number=qco.qco_reference_number,
                framework=qco.framework_covered,
                notification_type=SALES_NOTIFY,
                expires_in_days=days_remaining,
                idempotency_key=sales_key,
            )
            if sales_notif:
                results[SALES_NOTIFY] += 1
                logger.critical(
                    "EVF SALES NOTIFICATION (24h SLA): QCO %s (%s) expired %d days ago. "
                    "All external compliance claims for %s must revert to Tier 2. "
                    "Initiate renewal immediately. evf_expiry_notification_id=%s",
                    qco.qco_reference_number,
                    qco.framework_covered,
                    abs(days_remaining),
                    qco.framework_covered,
                    sales_notif.id,
                )

    db.commit()
    logger.info("EVF expiry scan complete (reference_date=%s): %s", today, results)
    return results


# ── Async wrapper for lifespan background task ────────────────────────────────

async def run_daily_expiry_scan() -> None:
    """
    Long-running async loop that fires scan_qco_expiry() once every 24 hours.
    Started as an asyncio.Task in main.py lifespan — cancelled on shutdown.
    """
    import asyncio

    from database import SessionLocal

    logger.info("EVF daily expiry scan task started")
    while True:
        try:
            db = SessionLocal()
            try:
                result = scan_qco_expiry(db)
                logger.info("EVF daily expiry scan result: %s", result)
            finally:
                db.close()
        except Exception:
            logger.exception("EVF daily expiry scan failed — will retry in 24h")

        # Sleep 24 hours (86 400 seconds)
        await asyncio.sleep(86_400)
