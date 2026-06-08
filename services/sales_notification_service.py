"""
Sales notification service (LIVE-006).

Fires a Slack webhook (or logs a warning) whenever a new DemoRequest is created.
The SARO Sales team receives an inbound lead notification within seconds of submission.

Configuration:
    SARO_SALES_WEBHOOK_URL   — Slack incoming webhook URL.
                                If unset, the notification is logged at WARNING
                                level but no exception is raised (safe fallback).

Usage::

    from services.sales_notification_service import notify_new_demo_request
    await notify_new_demo_request(record)           # from async context
    # or via BackgroundTasks:
    background_tasks.add_task(notify_new_demo_request_sync, record)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import requests as _requests

from models import DemoRequest

logger = logging.getLogger(__name__)

_WEBHOOK_URL_ENV = "SARO_SALES_WEBHOOK_URL"


def _build_slack_payload(record: DemoRequest) -> dict:
    """Build a Slack Block Kit message for a new demo request."""
    name = f"{record.first_name} {record.last_name}".strip()
    company = record.company_name or "—"
    message = (record.message or "—")[:300]
    submitted_at = (
        record.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if record.created_at
        else datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    return {
        "text": f"🚀 New SARO demo request from {name} ({company})",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚀 New Demo Request"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Name:*\n{name}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{record.email}"},
                    {"type": "mrkdwn", "text": f"*Company:*\n{company}"},
                    {"type": "mrkdwn", "text": f"*Submitted:*\n{submitted_at}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Message:*\n{message}"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in SARO Admin"},
                        "style": "primary",
                        "url": f"https://sarofrontend.fly.dev/app",
                    }
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Request ID: `{record.id}`"}
                ],
            },
        ],
    }


def notify_new_demo_request_sync(record: DemoRequest) -> None:
    """
    Synchronous notification — safe to call from FastAPI BackgroundTasks.

    Sends a Slack webhook with prospect details. If SARO_SALES_WEBHOOK_URL
    is not set or the webhook call fails, logs a warning and returns — never
    raises, so the demo signup response is never blocked.
    """
    webhook_url = os.environ.get(_WEBHOOK_URL_ENV, "").strip()
    if not webhook_url:
        logger.warning(
            "LIVE-006: %s not set — demo request from %s <%s> not dispatched to Sales. "
            "Set %s in Railway/Fly.io secrets to enable inbound lead alerts.",
            _WEBHOOK_URL_ENV,
            f"{record.first_name} {record.last_name}",
            record.email,
            _WEBHOOK_URL_ENV,
        )
        return

    payload = _build_slack_payload(record)
    try:
        resp = _requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info(
                "LIVE-006: Slack notification sent for demo request id=%s email=%s",
                record.id, record.email,
            )
        else:
            logger.warning(
                "LIVE-006: Slack webhook returned %s for demo request id=%s: %s",
                resp.status_code, record.id, resp.text[:200],
            )
    except Exception as exc:
        logger.warning(
            "LIVE-006: Slack webhook failed for demo request id=%s: %s",
            record.id, exc,
        )
