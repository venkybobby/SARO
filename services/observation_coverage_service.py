"""Observation-gap (coverage) attestations — adapter-independent core (STORY-COV-001).

SARO attests to when it was NOT observing — with cause and bounds — so coverage claims
are provable and gaps are disclosed rather than discovered. De-identified by construction
(INV-2): checkpoints and gaps carry only watermark positions and timestamps, never content.

Distinct from services/coverage_service.py (that is audit-recency staleness). This module
is observation-continuity: mirror-async blindness expressed as first-class gap evidence.

Scope: the adapter-independent core (checkpoint interface + gap/lag/report logic). The live
Bedrock-adapter heartbeat EMISSION (STORY-406) is deferred; a future adapter calls
record_checkpoint().
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from statistics import median
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from config import settings
from models import ObservationCheckpoint, ObservationGap, ObservationLagSample

logger = logging.getLogger(__name__)

# Cause classes (v1 closed set).
ADAPTER_FAILURE = "ADAPTER_FAILURE"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
CREDENTIAL_EXPIRY = "CREDENTIAL_EXPIRY"
DEPLOY_WINDOW = "DEPLOY_WINDOW"
LAG_EXCEEDED = "LAG_EXCEEDED"
PLANNED_MAINTENANCE = "PLANNED_MAINTENANCE"
SARO_OUTAGE = "SARO_OUTAGE"
UNKNOWN = "UNKNOWN"
CAUSE_CLASSES = frozenset(
    {
        ADAPTER_FAILURE,
        SOURCE_UNAVAILABLE,
        CREDENTIAL_EXPIRY,
        DEPLOY_WINDOW,
        LAG_EXCEEDED,
        PLANNED_MAINTENANCE,
        SARO_OUTAGE,
        UNKNOWN,
    }
)


class CoverageError(Exception):
    """Invalid cause class or coverage operation."""


def _aware(dt: datetime) -> datetime:
    """Normalize to aware UTC. Postgres TIMESTAMPTZ returns aware; the SQLite test
    harness returns naive — normalizing here lets the arithmetic work on both."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _open_gap(db: Session, tenant_id, system_id, adapter_id):
    return (
        db.query(ObservationGap)
        .filter(
            ObservationGap.tenant_id == tenant_id,
            ObservationGap.system_id == system_id,
            ObservationGap.adapter_id == adapter_id,
            ObservationGap.gap_end.is_(None),
        )
        .first()
    )


def _merge_intervals(
    intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Coalesce overlapping [lo, hi) intervals into their union (for blind-seconds math)."""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for lo, hi in ordered[1:]:
        last_lo, last_hi = merged[-1]
        if lo <= last_hi:
            merged[-1] = (last_lo, max(last_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _iso(dt: Optional[datetime]) -> str:
    return _aware(dt).isoformat() if dt is not None else ""


def _gap_payload(gap: ObservationGap) -> dict:
    return {
        "system_id": gap.system_id,
        "adapter_id": gap.adapter_id,
        "gap_start": _iso(gap.gap_start),
        "gap_end": _iso(gap.gap_end),
        "cause_class": gap.cause_class,
        "watermark_start": gap.watermark_start or "",
        "watermark_end": gap.watermark_end or "",
        "duration_seconds": gap.duration_seconds,
        "retroactive": gap.retroactive,
        "approver": gap.approver or "",
    }


def _finalize_gap_hash(db: Session, gap: ObservationGap) -> None:
    """Chain a FINALIZED gap into the tenant's gap evidence hash chain (AC-3).

    content_hash = SHA-256(canonical gap payload + prev_hash), where prev_hash is the
    tenant's most-recent already-finalized gap. Reuses the codebase's chain discipline.
    """
    prev = (
        db.query(ObservationGap.content_hash)
        .filter(
            ObservationGap.tenant_id == gap.tenant_id,
            ObservationGap.content_hash.isnot(None),
            ObservationGap.id != gap.id,
        )
        .order_by(ObservationGap.created_at.desc())
        .first()
    )
    prev_hash = prev[0] if prev else None
    gap.prev_hash = prev_hash
    payload = _gap_payload(gap)
    payload["prev_hash"] = prev_hash or "GENESIS"
    gap.content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _close_gap(
    gap: ObservationGap, *, end: datetime, watermark_end: Optional[str]
) -> None:
    gap.gap_end = end
    gap.watermark_end = watermark_end
    if gap.gap_start is not None:
        gap.duration_seconds = int(
            (_aware(end) - _aware(gap.gap_start)).total_seconds()
        )
    gap.updated_at = datetime.now(tz=timezone.utc)


# ── checkpoint interface (AC-1 core) ────────────────────────────────────────────
def record_checkpoint(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    system_id: str,
    adapter_id: str,
    watermark_position: str,
    watermark_timestamp: datetime,
) -> Optional[ObservationCheckpoint]:
    """Persist a heartbeat/watermark. Idempotent per (tenant, system, adapter, position).

    A checkpoint arriving while a gap is open CLOSES that gap (observation resumed).
    Returns the checkpoint, or None if it was an idempotent duplicate.
    """
    existing = (
        db.query(ObservationCheckpoint)
        .filter(
            ObservationCheckpoint.tenant_id == tenant_id,
            ObservationCheckpoint.system_id == system_id,
            ObservationCheckpoint.adapter_id == adapter_id,
            ObservationCheckpoint.watermark_position == watermark_position,
        )
        .first()
    )
    if existing is not None:
        return None  # duplicate window re-read — do not double-record

    cp = ObservationCheckpoint(
        tenant_id=tenant_id,
        system_id=system_id,
        adapter_id=adapter_id,
        watermark_position=watermark_position,
        watermark_timestamp=watermark_timestamp,
    )
    db.add(cp)
    gap = _open_gap(db, tenant_id, system_id, adapter_id)
    if gap is not None:
        _close_gap(gap, end=watermark_timestamp, watermark_end=watermark_position)
        _finalize_gap_hash(db, gap)  # chain the now-finalized gap (AC-3)
    db.commit()
    db.refresh(cp)
    return cp


# ── gap detection (AC-2) ─────────────────────────────────────────────────────────
def detect_gaps(
    db: Session,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    now: Optional[datetime] = None,
    cadence_seconds: Optional[int] = None,
) -> list[ObservationGap]:
    """Open a gap for any (system, adapter) whose latest checkpoint is older than the
    configured cadence + tolerance and that has no open gap. Cause = UNKNOWN until diagnosed."""
    now = now or datetime.now(tz=timezone.utc)
    cadence = (
        cadence_seconds
        if cadence_seconds is not None
        else settings.saro_coverage_cadence_seconds
    )

    q = db.query(ObservationCheckpoint)
    if tenant_id is not None:
        q = q.filter(ObservationCheckpoint.tenant_id == tenant_id)

    latest: dict[tuple, ObservationCheckpoint] = {}
    for cp in q.all():
        key = (cp.tenant_id, cp.system_id, cp.adapter_id)
        if (
            key not in latest
            or cp.watermark_timestamp > latest[key].watermark_timestamp
        ):
            latest[key] = cp

    opened: list[ObservationGap] = []
    for (tid, sid, aid), cp in latest.items():
        if (_aware(now) - _aware(cp.watermark_timestamp)).total_seconds() <= cadence:
            continue
        if _open_gap(db, tid, sid, aid) is not None:
            continue
        gap = ObservationGap(
            tenant_id=tid,
            system_id=sid,
            adapter_id=aid,
            gap_start=cp.watermark_timestamp,
            cause_class=UNKNOWN,
            detection_method="checkpoint_cadence_monitor",
            watermark_start=cp.watermark_position,
        )
        db.add(gap)
        opened.append(gap)
    db.commit()
    for g in opened:
        db.refresh(g)
    return opened


def diagnose_gap(db: Session, gap_id: uuid.UUID, cause_class: str) -> ObservationGap:
    """Set a diagnosed cause on an UNKNOWN gap (AC-2)."""
    if cause_class not in CAUSE_CLASSES:
        raise CoverageError(f"unknown cause_class: {cause_class}")
    gap = db.get(ObservationGap, gap_id)
    if gap is None:
        raise CoverageError("gap not found")
    gap.cause_class = cause_class
    gap.updated_at = datetime.now(tz=timezone.utc)
    # If the gap was already finalized (closed), re-seal its content_hash over the new
    # cause, keeping its chain position (prev_hash) so the chain stays consistent.
    if gap.content_hash is not None:
        payload = _gap_payload(gap)
        payload["prev_hash"] = gap.prev_hash or "GENESIS"
        gap.content_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    db.commit()
    db.refresh(gap)
    return gap


def verify_gap_chain(db: Session, tenant_id: uuid.UUID) -> dict:
    """Recompute the tenant's finalized-gap hash chain; flag the first tampered gap (AC-3)."""
    gaps = (
        db.query(ObservationGap)
        .filter(
            ObservationGap.tenant_id == tenant_id,
            ObservationGap.content_hash.isnot(None),
        )
        .order_by(ObservationGap.created_at.asc())
        .all()
    )
    prev_hash: Optional[str] = None
    for i, g in enumerate(gaps):
        payload = _gap_payload(g)
        payload["prev_hash"] = prev_hash or "GENESIS"
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        if g.prev_hash != prev_hash or g.content_hash != expected:
            return {"valid": False, "break_at_index": i, "gap_id": str(g.id)}
        prev_hash = g.content_hash
    return {"valid": True, "gaps_checked": len(gaps)}


# ── SARO self-outage (edge) ─────────────────────────────────────────────────────
def detect_saro_outage(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    system_id: str,
    adapter_id: str,
    downtime_start: datetime,
    downtime_end: datetime,
) -> ObservationGap:
    """On restart, confess SARO's own downtime as a RETROACTIVE SARO_OUTAGE gap (edge)."""
    gap = ObservationGap(
        tenant_id=tenant_id,
        system_id=system_id,
        adapter_id=adapter_id,
        gap_start=downtime_start,
        gap_end=downtime_end,
        cause_class=SARO_OUTAGE,
        detection_method="boot_discontinuity",
        retroactive=True,
        duration_seconds=int(
            (_aware(downtime_end) - _aware(downtime_start)).total_seconds()
        ),
    )
    db.add(gap)
    db.flush()
    _finalize_gap_hash(db, gap)  # created-closed -> chain immediately (AC-3)
    db.commit()
    db.refresh(gap)
    return gap


# ── planned maintenance (edge) ──────────────────────────────────────────────────
def declare_maintenance(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    system_id: str,
    adapter_id: str,
    start: datetime,
    end: datetime,
    approver: str,
) -> ObservationGap:
    """Pre-declare a maintenance window — a PLANNED_MAINTENANCE gap with an approver."""
    gap = ObservationGap(
        tenant_id=tenant_id,
        system_id=system_id,
        adapter_id=adapter_id,
        gap_start=start,
        gap_end=end,
        cause_class=PLANNED_MAINTENANCE,
        detection_method="pre_declared",
        approver=approver,
        duration_seconds=int((_aware(end) - _aware(start)).total_seconds()),
    )
    db.add(gap)
    db.flush()
    _finalize_gap_hash(db, gap)  # pre-declared closed gap -> chain immediately (AC-3)
    db.commit()
    db.refresh(gap)
    return gap


# ── lag metrics (AC-5) ───────────────────────────────────────────────────────────
def _percentile(values: Sequence[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return float(ordered[k])


def record_lag_sample(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    system_id: str,
    adapter_id: str,
    window_bucket: str,
    samples_ms: Sequence[float],
) -> ObservationLagSample:
    """Record p50/p95/max observation lag for a window (measured evidence, not an estimate)."""
    p50 = float(median(samples_ms)) if samples_ms else 0.0
    p95 = _percentile(samples_ms, 95)
    mx = float(max(samples_ms)) if samples_ms else 0.0
    row = (
        db.query(ObservationLagSample)
        .filter(
            ObservationLagSample.tenant_id == tenant_id,
            ObservationLagSample.system_id == system_id,
            ObservationLagSample.adapter_id == adapter_id,
            ObservationLagSample.window_bucket == window_bucket,
        )
        .first()
    )
    if row is None:
        row = ObservationLagSample(
            tenant_id=tenant_id,
            system_id=system_id,
            adapter_id=adapter_id,
            window_bucket=window_bucket,
            p50_ms=p50,
            p95_ms=p95,
            max_ms=mx,
        )
        db.add(row)
    else:
        row.p50_ms, row.p95_ms, row.max_ms = p50, p95, mx
    db.commit()
    db.refresh(row)
    return row


# ── coverage report (AC-4) ───────────────────────────────────────────────────────
def coverage_report(
    db: Session,
    tenant_id: uuid.UUID,
    system_id: str,
    start: datetime,
    end: datetime,
) -> dict:
    """% time under observation, gap list with causes, max observation lag, methodology (AC-4)."""
    start, end = _aware(start), _aware(end)
    total = max(1.0, (end - start).total_seconds())
    gaps = (
        db.query(ObservationGap)
        .filter(
            ObservationGap.tenant_id == tenant_id,
            ObservationGap.system_id == system_id,
            ObservationGap.gap_start < end,
        )
        .all()
    )
    # Clip each gap to the window, then MERGE overlapping intervals so simultaneous gaps
    # (two adapters blind at once, maintenance overlapping a detected gap) are the UNION,
    # not double-counted (reviewer S2). Gaps fully outside the window are excluded.
    intervals: list[tuple[datetime, datetime]] = []
    gap_list = []
    for g in gaps:
        g_start = _aware(g.gap_start)
        g_end = (
            _aware(g.gap_end) if g.gap_end else end
        )  # ongoing gaps count to window end
        lo, hi = max(g_start, start), min(g_end, end)
        if hi <= lo:
            continue  # fully outside the window
        intervals.append((lo, hi))
        gap_list.append(
            {
                "id": str(g.id),
                "cause_class": g.cause_class,
                "gap_start": g.gap_start.isoformat(),
                "gap_end": g.gap_end.isoformat() if g.gap_end else None,
                "ongoing": g.gap_end is None,
                "approver": g.approver,
                "detection_method": g.detection_method,
                "retroactive": g.retroactive,
            }
        )
    blind_seconds = sum(
        (hi - lo).total_seconds() for lo, hi in _merge_intervals(intervals)
    )
    coverage_pct = round(max(0.0, 1.0 - min(blind_seconds, total) / total) * 100, 3)

    # Max lag WITHIN the report window (reviewer S3).
    max_lag = (
        db.query(ObservationLagSample.max_ms)
        .filter(
            ObservationLagSample.tenant_id == tenant_id,
            ObservationLagSample.system_id == system_id,
            ObservationLagSample.recorded_at >= start,
            ObservationLagSample.recorded_at <= end,
        )
        .order_by(ObservationLagSample.max_ms.desc())
        .first()
    )
    return {
        "system_id": system_id,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "coverage_pct": coverage_pct,
        "gaps": gap_list,
        "max_observation_lag_ms": float(max_lag[0])
        if max_lag and max_lag[0] is not None
        else None,
        "methodology": (
            "Coverage = 1 - (blind seconds / window seconds), where blind seconds are the union "
            "of observation-gap intervals overlapping the window. Gaps carry cause class + watermark "
            "bounds (positions/timestamps only, no observed content). Max lag is the measured "
            "per-window maximum, not an estimate. Ongoing gaps count to the window end."
        ),
    }
