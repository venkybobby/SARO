"""Notification service — threshold breach detection with duplicate suppression.

Called as a post-scan hook from routers/scan.py after each completed scan.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import Notification

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 70


def _get_tenant_threshold(db: Session, tenant_id, regulation: str) -> int:
    """Return the compliance alert threshold for a tenant/regulation pair.

    Falls back to the global default (70) until tenant_settings table exists.
    """
    # TODO: replace with DB lookup once tenant_settings table is added
    return _DEFAULT_THRESHOLD


def _has_unread_duplicate(db: Session, tenant_id, notif_type: str, regulation: str) -> bool:
    """Return True if an unread notification of the same type+regulation already exists."""
    return (
        db.query(Notification)
        .filter(
            Notification.tenant_id == tenant_id,
            Notification.type == notif_type,
            Notification.read_at.is_(None),
            Notification.metadata_json.contains(f'"regulation": "{regulation}"'),
        )
        .first()
        is not None
    )


def generate_threshold_notification(
    db: Session,
    tenant_id,
    score: float,
    threshold: int,
    regulation: str,
) -> Notification | None:
    """Insert a threshold_breach notification if score < threshold and no unread duplicate.

    Returns the created Notification or None if suppressed.
    """
    if score >= threshold:
        return None

    if _has_unread_duplicate(db, tenant_id, "threshold_breach", regulation):
        logger.debug(
            "Suppressing duplicate threshold_breach notification for tenant=%s regulation=%s",
            tenant_id,
            regulation,
        )
        return None

    severity = "critical" if score < threshold * 0.5 else "high"
    notif = Notification(
        tenant_id=tenant_id,
        type="threshold_breach",
        title=f"{regulation} compliance score dropped to {score:.0f}%",
        body=(
            f"Your {regulation} compliance score ({score:.0f}) is below the configured "
            f"threshold ({threshold}). Immediate review recommended."
        ),
        severity=severity,
        metadata_json=f'{{"regulation": "{regulation}", "score": {score}, "threshold": {threshold}}}',
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    logger.info(
        "Created threshold_breach notification id=%s tenant=%s regulation=%s score=%s",
        notif.id,
        tenant_id,
        regulation,
        score,
    )
    return notif


def generate_drift_notification(
    db: Session,
    tenant_id,
    framework: str,
    current_version: str,
    latest_version: str,
    affected_packs: list[str],
) -> Notification | None:
    """Insert a drift_alert notification when a framework publishes a new version."""
    if _has_unread_duplicate(db, tenant_id, "drift_alert", framework):
        return None

    notif = Notification(
        tenant_id=tenant_id,
        type="drift_alert",
        title=f"{framework} updated to {latest_version} (current: {current_version})",
        body=(
            f"A new version of {framework} is available. "
            f"Affected rule packs: {', '.join(affected_packs) or 'none'}."
        ),
        severity="high",
        metadata_json=(
            f'{{"regulation": "{framework}", "current_version": "{current_version}", '
            f'"latest_version": "{latest_version}"}}'
        ),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def get_unread_count(db: Session, tenant_id) -> int:
    """Return unread notification count for a tenant (fast indexed query)."""
    return (
        db.query(Notification)
        .filter(Notification.tenant_id == tenant_id, Notification.read_at.is_(None))
        .count()
    )
