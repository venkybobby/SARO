"""Notification service — threshold breach detection with duplicate suppression.

Called as a post-scan hook from routers/scan.py after each completed scan.

SPEC-F5: SSE connection registry + SendGrid email dispatch for critical/high alerts.
"""
from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy.orm import Session

from models import Notification

logger = logging.getLogger(__name__)

# ── SPEC-F5: SSE connection registry ────────────────────────────────────────
# Maps tenant_id (str) → list of asyncio.Queue for live SSE subscribers.

_sse_connections: dict[str, list[asyncio.Queue]] = {}


def register_sse_connection(tenant_id: str) -> asyncio.Queue:
    """Register a new SSE subscriber queue for a tenant."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_connections.setdefault(str(tenant_id), []).append(q)
    return q


def unregister_sse_connection(tenant_id: str, q: asyncio.Queue) -> None:
    """Remove a disconnected SSE subscriber queue."""
    if str(tenant_id) in _sse_connections:
        try:
            _sse_connections[str(tenant_id)].remove(q)
        except ValueError:
            pass


async def push_sse_event(tenant_id: str, event: dict) -> None:
    """Push an event dict to all connected SSE subscribers for a tenant."""
    queues = _sse_connections.get(str(tenant_id), [])
    for q in list(queues):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def dispatch_notification(db: Session, notification: Notification) -> None:
    """Dispatch a notification via SSE push + email (critical/high only)."""
    try:
        # SSE push (fire-and-forget in running event loop if available)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                push_sse_event(
                    str(notification.tenant_id),
                    {
                        "id": str(notification.id),
                        "type": notification.type,
                        "title": notification.title,
                        "severity": notification.severity,
                    },
                )
            )
        except RuntimeError:
            pass  # No running event loop — SSE push skipped

        # Email for critical/high severity
        if notification.severity in ("critical", "high"):
            from models import User

            users = (
                db.query(User)
                .filter(
                    User.tenant_id == notification.tenant_id,
                    User.is_active == True,  # noqa: E712
                )
                .all()
            )
            for user in users:
                _send_email(user.email, notification)
    except Exception as exc:
        logger.warning("Notification dispatch error: %s", exc)


def _send_email(recipient: str, notification: Notification) -> None:
    """Send an alert email via SendGrid. Skips silently if no API key configured."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        logger.info(
            "Email dispatch skipped: no SENDGRID_API_KEY (would send to %s)", recipient
        )
        return
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        html_content = (
            f"<h2>SARO Alert: {notification.title}</h2>"
            f"<p><strong>Severity:</strong> {notification.severity.upper()}</p>"
            f"<p>{notification.body}</p>"
            f"<p><a href='https://saro.app/dashboard'>View in SARO Dashboard</a></p>"
        )
        plain_content = (
            f"SARO Alert: {notification.title}\n"
            f"Severity: {notification.severity.upper()}\n"
            f"{notification.body}"
        )
        mail = Mail(
            from_email="alerts@saro.app",
            to_emails=recipient,
            subject=f"[SARO] {notification.severity.upper()}: {notification.title}",
            html_content=html_content,
            plain_text_content=plain_content,
        )
        sg.send(mail)
        logger.info(
            "Alert email sent to %s for notification %s", recipient, notification.id
        )
    except Exception as exc:
        logger.warning("SendGrid email failed for %s: %s", recipient, exc)

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
