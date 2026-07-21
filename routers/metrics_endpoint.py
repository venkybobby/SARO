"""Prometheus scrape endpoint (STORY-368).

Authenticated by a bearer token from ``METRICS_TOKEN`` — **fail closed**. When
the variable is unset no valid credential exists, so every request is rejected.
That is deliberate: "open when unconfigured" is exactly the pattern already
flagged as a hazard for CORS in ``main.py``, and metrics are a free liveness and
traffic-shape oracle for anyone probing the service.

Gauges that need a live reading (database reachability, ingestion lag) are
computed at scrape time and each failure is contained — a metrics endpoint that
500s during an incident is useless precisely when it is needed.
"""

from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

import services.metrics as metrics
from database import get_db, health_check

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])

# auto_error=False so a missing header produces our own 401 rather than a 403.
_bearer = HTTPBearer(auto_error=False)


def _require_metrics_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    configured = os.environ.get("METRICS_TOKEN", "")
    supplied = credentials.credentials if credentials else ""
    # Constant-time compare; an unconfigured token compares against "" and can
    # never match a non-empty credential, so the endpoint stays closed.
    if not configured or not supplied or not hmac.compare_digest(configured, supplied):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="metrics scrape requires a valid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _refresh_db_gauge() -> None:
    try:
        metrics.DB_REACHABLE.set(1 if health_check().get("ok") else 0)
    except Exception:  # noqa: BLE001 — never fail the scrape on a probe error
        metrics.DB_REACHABLE.set(0)


def _refresh_ingestion_lag(db: Session) -> None:
    """Age of the newest observation watermark, across all tenants.

    Deliberately a global max with no tenant breakdown (INV-3): the operator
    needs to know ingestion stalled, not whose it was — that question is
    answered inside the product, behind authorization.
    """
    try:
        from models import ObservationCheckpoint

        newest = db.query(func.max(ObservationCheckpoint.watermark_timestamp)).scalar()
        if newest is None:
            metrics.INGESTION_LAG.set(-1)  # unknown, distinct from "zero lag"
            return
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        lag = (datetime.now(tz=timezone.utc) - newest).total_seconds()
        metrics.INGESTION_LAG.set(max(lag, 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingestion lag gauge unavailable: %s", exc)
        metrics.INGESTION_LAG.set(-1)


@router.get(
    "/metrics",
    dependencies=[Depends(_require_metrics_token)],
    summary="Prometheus metrics (bearer token required; global aggregates only)",
    response_class=Response,
)
def metrics_endpoint(db: Session = Depends(get_db)) -> Response:
    _refresh_db_gauge()
    _refresh_ingestion_lag(db)

    try:
        from main import app  # local import: avoids a circular import at module load

        version = getattr(app, "version", "unknown")
    except Exception:  # noqa: BLE001
        version = "unknown"

    return Response(
        content=metrics.render_exposition(version=version),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
