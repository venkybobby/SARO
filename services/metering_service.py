"""PHI-free usage metering (STORY-MTR-001).

Per-tenant, per-period consumption counters that are PHI-free BY CONSTRUCTION: a meter
record carries only a closed-vocabulary key, a period bucket, a count, and closed-
vocabulary dimension tags. No free-text field exists, so payload/PII leakage is
structurally impossible (INV-2 by construction, not by redaction).

Async posture: increments are emitted post-evidence-persist and are best-effort —
metering must NEVER fail or delay an evaluation. Lost increments are acceptable and
bounded/measured by daily reconciliation; blocked evaluations are not.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import (
    GRCEvidenceRecord,
    Notification,
    UsageMeter,
    UsageMeterIdempotency,
    UsageStatement,
)

logger = logging.getLogger(__name__)

# Closed meter vocabulary (v1). An unknown key is a programming error — reject it.
EVALUATIONS_EXECUTED = "evaluations_executed"
ATTESTATIONS_ISSUED = "attestations_issued"
EVIDENCE_RECORDS_PERSISTED = "evidence_records_persisted"
COVERAGE_REPORT_GENERATIONS = "coverage_report_generations"
CRITERIA_REPRODUCTIONS = "criteria_reproductions"
ACTIVE_OBSERVED_SYSTEMS = "active_observed_systems"
ADAPTER_OBSERVATION_VOLUME = "adapter_observation_volume"
METER_KEYS = frozenset(
    {
        EVALUATIONS_EXECUTED,
        ATTESTATIONS_ISSUED,
        EVIDENCE_RECORDS_PERSISTED,
        COVERAGE_REPORT_GENERATIONS,
        CRITERIA_REPRODUCTIONS,
        ACTIVE_OBSERVED_SYSTEMS,
        ADAPTER_OBSERVATION_VOLUME,
    }
)

# Closed dimension vocabulary — the ONLY allowed dimension tag keys (no free text).
DIMENSION_KEYS = frozenset({"gate_id", "vertical", "adapter_id", "outcome"})
# Per-key closed value allow-lists (None = any bounded scalar). `outcome` is enum-bounded.
_DIMENSION_VALUES: dict[str, Optional[frozenset]] = {
    "outcome": frozenset({"GO", "GO_WITH_CONDITIONS", "NO_GO", "unknown"}),
    "gate_id": None,
    "vertical": None,
    "adapter_id": None,
}
# Even where values are open, they are bounded scalars with a hard length cap so a
# caller can never smuggle payload/PII into the meter (AC-1 by construction, not redaction).
_MAX_DIMENSION_VALUE_LEN = 64


class MeteringError(Exception):
    """Invalid meter key or dimension (closed-vocabulary violation)."""


def current_period(now: Optional[datetime] = None) -> str:
    """UTC period bucket 'YYYY-MM' at emission time (tenant-local display is presentation)."""
    return (now or datetime.now(tz=timezone.utc)).strftime("%Y-%m")


def _period_range(period: str) -> tuple[datetime, datetime]:
    """Return [start, next_month) UTC datetimes for a 'YYYY-MM' bucket (portable, no to_char)."""
    year, month = (int(x) for x in period.split("-"))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + (month // 12), (month % 12) + 1, 1, tzinfo=timezone.utc)
    return start, end


def _validate(meter_key: str, dimensions: dict) -> None:
    if meter_key not in METER_KEYS:
        raise MeteringError(f"unknown meter_key: {meter_key}")
    unknown = set(dimensions) - DIMENSION_KEYS
    if unknown:
        raise MeteringError(
            f"free-text/unknown dimension keys forbidden: {sorted(unknown)}"
        )
    # Bound VALUES too, so PHI-freeness is by construction regardless of caller
    # (security review): scalars only, hard length cap, closed allow-list where defined.
    for key, value in dimensions.items():
        if not isinstance(value, (str, int, bool)):
            raise MeteringError(
                f"dimension '{key}' must be a bounded scalar, not {type(value).__name__}"
            )
        allowed = _DIMENSION_VALUES.get(key)
        if allowed is not None and str(value) not in allowed:
            raise MeteringError(f"dimension '{key}' value not in the closed allow-list")
        if isinstance(value, str) and len(value) > _MAX_DIMENSION_VALUE_LEN:
            raise MeteringError(
                f"dimension '{key}' value exceeds {_MAX_DIMENSION_VALUE_LEN} chars "
                "(possible payload smuggling — rejected)"
            )


def _dims_hash(dimensions: dict) -> str:
    return hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def increment(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    meter_key: str,
    period: Optional[str] = None,
    dimensions: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
    amount: int = 1,
) -> Optional[UsageMeter]:
    """Idempotently add ``amount`` to a meter. Returns the row, or None if deduped.

    Raises MeteringError for a closed-vocabulary violation (a coding error, surfaced
    loudly rather than silently metering garbage).
    """
    dimensions = dict(dimensions or {})
    _validate(meter_key, dimensions)
    period = period or current_period()

    if idempotency_key is not None:
        if db.get(UsageMeterIdempotency, idempotency_key) is not None:
            return None  # already counted this logical invocation
        db.add(UsageMeterIdempotency(idempotency_key=idempotency_key))

    dh = _dims_hash(dimensions)
    row = (
        db.query(UsageMeter)
        .filter(
            UsageMeter.tenant_id == tenant_id,
            UsageMeter.meter_key == meter_key,
            UsageMeter.period_bucket == period,
            UsageMeter.dimensions_hash == dh,
        )
        .with_for_update()
        .first()
    )
    if row is None:
        row = UsageMeter(
            tenant_id=tenant_id,
            meter_key=meter_key,
            period_bucket=period,
            dimensions=dimensions,
            dimensions_hash=dh,
            count=amount,
        )
        db.add(row)
    else:
        row.count += amount
        row.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def safe_increment(db: Session, **kwargs) -> None:
    """Fail-open increment for hot paths — a metering failure never blocks the caller.

    After a successful increment, checks the configured threshold for that meter
    (best-effort) so AC-4 threshold notifications actually fire at runtime.
    """
    try:
        row = increment(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 — metering must never break the evaluation path
        db.rollback()
        logger.warning("usage metering failed (continuing): %s", exc)
        return
    if row is None:
        return  # deduped
    try:
        check_threshold(
            db, kwargs["tenant_id"], kwargs["meter_key"], kwargs.get("period")
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("usage threshold check failed (continuing): %s", exc)


def record_high_water(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    meter_key: str,
    value: int,
    period: Optional[str] = None,
    dimensions: Optional[dict] = None,
) -> UsageMeter:
    """Set a high-water-mark meter (e.g. active_observed_systems) to max(current, value)."""
    dimensions = dict(dimensions or {})
    _validate(meter_key, dimensions)
    period = period or current_period()
    dh = _dims_hash(dimensions)
    row = (
        db.query(UsageMeter)
        .filter(
            UsageMeter.tenant_id == tenant_id,
            UsageMeter.meter_key == meter_key,
            UsageMeter.period_bucket == period,
            UsageMeter.dimensions_hash == dh,
        )
        .first()
    )
    if row is None:
        row = UsageMeter(
            tenant_id=tenant_id,
            meter_key=meter_key,
            period_bucket=period,
            dimensions=dimensions,
            dimensions_hash=dh,
            count=value,
        )
        db.add(row)
    elif value > row.count:
        row.count = value
        row.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def meter_totals(db: Session, tenant_id: uuid.UUID, period: str) -> dict[str, int]:
    rows = (
        db.query(UsageMeter)
        .filter(UsageMeter.tenant_id == tenant_id, UsageMeter.period_bucket == period)
        .all()
    )
    totals: dict[str, int] = {}
    for r in rows:
        totals[r.meter_key] = totals.get(r.meter_key, 0) + r.count
    return totals


def generate_statement(
    db: Session, tenant_id: uuid.UUID, period: str
) -> UsageStatement:
    """Issue (or return the already-issued) immutable usage statement for a period (AC-3)."""
    existing = (
        db.query(UsageStatement)
        .filter(
            UsageStatement.tenant_id == tenant_id,
            UsageStatement.period_bucket == period,
        )
        .first()
    )
    if existing is not None:
        return existing  # immutable once issued
    totals = meter_totals(db, tenant_id, period)
    payload = {"tenant_id": str(tenant_id), "period": period, "totals": totals}
    content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    stmt = UsageStatement(
        tenant_id=tenant_id,
        period_bucket=period,
        totals=totals,
        content_hash=content_hash,
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)
    return stmt


def check_threshold(
    db: Session, tenant_id: uuid.UUID, meter_key: str, period: Optional[str] = None
) -> bool:
    """Record + notify on a threshold crossing (AC-4). NEVER enforces a cutoff."""
    thresholds = settings.saro_metering_thresholds or {}
    limit = thresholds.get(meter_key)
    if limit is None:  # 0 is a legitimate "record every use" threshold
        return False
    period = period or current_period()
    total = meter_totals(db, tenant_id, period).get(meter_key, 0)
    if total < limit:
        return False
    db.add(
        Notification(
            tenant_id=tenant_id,
            type="usage_threshold",
            title=f"Usage threshold crossed: {meter_key}",
            body=f"{meter_key} reached {total} (limit {limit}) for {period}. "
            f"No cutoff applied — evaluations continue.",
            severity="medium",
        )
    )
    db.commit()
    return True


def reconcile(db: Session, tenant_id: uuid.UUID, period: Optional[str] = None) -> dict:
    """Daily reconciliation (AC-5): cross-check meters vs authoritative counts.

    Drift beyond the configured tolerance raises a data-quality finding (Notification).
    v1 reconciles evidence_records_persisted against grc_evidence_records.
    """
    period = period or current_period()
    metered = meter_totals(db, tenant_id, period).get(EVIDENCE_RECORDS_PERSISTED, 0)
    # Period-scope the authoritative count to the SAME period as the meter (reviewer B1:
    # comparing a monthly meter against an all-time count false-fires once a tenant
    # spans >1 period). Portable UTC month range [start, next_month).
    start, end = _period_range(period)
    authoritative = (
        db.query(GRCEvidenceRecord)
        .filter(
            GRCEvidenceRecord.tenant_id == tenant_id,
            GRCEvidenceRecord.created_at >= start,
            GRCEvidenceRecord.created_at < end,
        )
        .count()
    )
    drift = 0.0 if authoritative == 0 else abs(metered - authoritative) / authoritative
    ok = drift <= settings.saro_metering_drift_tolerance
    if not ok:
        db.add(
            Notification(
                tenant_id=tenant_id,
                type="data_quality",
                title="Usage metering drift exceeds tolerance",
                body=f"evidence_records_persisted metered={metered} authoritative={authoritative} "
                f"drift={drift:.3%} (> {settings.saro_metering_drift_tolerance:.3%}).",
                severity="high",
            )
        )
        db.commit()
    return {
        "meter_key": EVIDENCE_RECORDS_PERSISTED,
        "metered": metered,
        "authoritative": authoritative,
        "drift": round(drift, 4),
        "within_tolerance": ok,
    }
