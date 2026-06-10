"""Notification REST endpoints (SPEC-F5).

GET  /api/v1/notifications                paginated list, filter by read/severity
GET  /api/v1/notifications/unread-count   fast unread count (≤50 ms SLA)
GET  /api/v1/notifications/stream         SSE real-time stream (SPEC-F5 FR-03)
PATCH /api/v1/notifications/{id}/read     mark single notification read
POST  /api/v1/notifications/read-all      mark all unread as read
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Notification, User
from services.notification_service import get_unread_count

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _notif_to_dict(n: Notification) -> dict[str, Any]:
    return {
        "id": str(n.id),
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "severity": n.severity,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "metadata": n.metadata_json,
    }


@router.get("", summary="List notifications for the authenticated tenant")
def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = Query(default=False, description="Filter to unread notifications only"),
    severity: str | None = Query(default=None, description="Filter by severity: critical|high|medium|low"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    q = db.query(Notification).filter(Notification.tenant_id == current_user.tenant_id)

    if unread_only:
        q = q.filter(Notification.read_at.is_(None))

    if severity:
        q = q.filter(Notification.severity == severity)

    total = q.count()
    unread = get_unread_count(db, current_user.tenant_id)

    items = (
        q.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [_notif_to_dict(n) for n in items],
        "unread_count": unread,
        "total": total,
    }


@router.get("/unread-count", summary="Fast unread notification count (≤50ms)")
def unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    return {"unread_count": get_unread_count(db, current_user.tenant_id)}


@router.patch("/{notification_id}/read", summary="Mark a notification as read")
def mark_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notif.read_at is None:
        notif.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notif)

    return _notif_to_dict(notif)


@router.post("/read-all", summary="Mark all unread notifications as read")
def mark_all_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    affected = (
        db.query(Notification)
        .filter(
            Notification.tenant_id == current_user.tenant_id,
            Notification.read_at.is_(None),
        )
        .update({"read_at": now}, synchronize_session=False)
    )
    db.commit()
    return {"marked_read": affected}


# ── SPEC-F5: SSE real-time stream ─────────────────────────────────────────────


@router.get("/stream", summary="SSE real-time notification stream (SPEC-F5 FR-03)")
async def notification_stream(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """
    Server-Sent Events stream for real-time in-app bell-icon notifications.
    Heartbeat ping every 30s keeps Railway proxy connection alive.

    SARO-H10: this endpoint requires Authorization: Bearer like every other
    route. The browser-native EventSource API cannot set custom headers, so
    frontend consumers MUST use fetch() + ReadableStream (with the bearer
    token attached) rather than `new EventSource(...)`.
    """
    from services.notification_service import (
        register_sse_connection,
        unregister_sse_connection,
    )

    tenant_id = str(current_user.tenant_id)
    q = register_sse_connection(tenant_id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            unregister_sse_connection(tenant_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
