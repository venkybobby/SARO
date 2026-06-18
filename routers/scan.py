"""
/api/v1/scan  — inline batch scanning endpoints.

POST /api/v1/scan          — standard BatchIn (samples[].text format)
POST /api/v1/scan/data     — saro_data framework format (model_outputs[].output)
GET  /api/v1/audits        — list audits for the caller's tenant
GET  /api/v1/audits/{id}   — fetch a specific audit report
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    require_role,
    require_role_or_persona,
    TRACE_READ_ROLES,
    TRACE_READ_PERSONAS,
)
from database import get_db
from engine import SARoEngine
from models import Audit, AuditTrace, SampleFinding, ScanReport, User
from schemas import (
    AuditListItemOut,
    AuditReportOut,
    BatchIn,
    SARoDataBatchIn,
)
from services.hash_chain_service import LEGACY_SENTINEL, compute_event_hash
from sqlalchemy import text as _sql_text

# STORY-TRACE-003: the AI Auditor's screen lists audits and opens audit detail.
# Grant the audit/compliance personas read access alongside the legacy roles.
# The list additionally preserves the existing read-only `demo_viewer` role.
_require_audits_list_read = require_role_or_persona(
    TRACE_READ_ROLES + ("demo_viewer",), TRACE_READ_PERSONAS
)
_require_audit_detail_read = require_role_or_persona(
    TRACE_READ_ROLES, TRACE_READ_PERSONAS
)


# ── SAR-008: risk notification thresholds ────────────────────────────────────
_NOTIF_CRITICAL_THRESHOLD = 0.80   # risk score ≥ 80 → critical alert
_NOTIF_HIGH_THRESHOLD = 0.60       # risk score ≥ 60 → high alert


def _maybe_dispatch_risk_notification(
    db: Session,
    tenant_id,
    audit_id,
    overall_risk: float,
    dataset_name: str,
) -> None:
    """
    Create and dispatch a Notification when a batch scan exceeds risk thresholds.

    Thresholds (configurable via _NOTIF_* constants):
      ≥ 0.80 → severity=critical  (threshold_breach)
      ≥ 0.60 → severity=high      (threshold_breach)

    Non-blocking: any exception is logged and swallowed so the scan
    response is never delayed or failed by notification side-effects.
    """
    from models import Notification
    from services.notification_service import dispatch_notification

    if overall_risk < _NOTIF_HIGH_THRESHOLD:
        return

    severity = "critical" if overall_risk >= _NOTIF_CRITICAL_THRESHOLD else "high"
    risk_pct = round(overall_risk * 100, 1)

    try:
        notif = Notification(
            tenant_id=tenant_id,
            type="threshold_breach",
            title=f"Risk threshold exceeded — {dataset_name}",
            body=(
                f"Audit {audit_id} scored {risk_pct}/100 risk. "
                f"Severity: {severity.upper()}. "
                "Review findings and remediation guidance in the TRACE tab."
            ),
            severity=severity,
            metadata_json=f'{{"audit_id": "{audit_id}", "risk_score": {risk_pct}}}',
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        dispatch_notification(db, notif)
        logger.info(
            "Risk notification dispatched: audit=%s risk=%.1f severity=%s",
            audit_id, risk_pct, severity,
        )
    except Exception as exc:
        logger.warning("Risk notification failed (non-fatal): %s", exc)
        try:
            db.rollback()
        except Exception:
            pass

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["scan"])


def _dedupe_findings(findings: list[dict]) -> list[dict]:
    """PT-002: collapse sample findings to one row per (sample_id, domain, matched_signal).

    Identical re-matches are dropped; distinct samples are preserved. First-seen order
    is retained so the persisted set is deterministic.
    """
    seen: set[tuple] = set()
    out: list[dict] = []
    for f in findings:
        key = (f["sample_id"], f["domain"], f["matched_signal"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _persist_traces(engine: SARoEngine, audit_id: uuid.UUID, db: Session) -> None:
    """Persist trace records and sample findings accumulated by the engine.

    AUD-001: each AuditTrace is hash-chained. build_event_payload() from
    hash_chain_service constructs the canonical dict so the write path and
    the verify path always hash identical field sets.

    Hash chain writes are CRITICAL — a failure here raises so the caller
    knows audit evidence was not generated. Sample-finding writes are
    non-critical and failures are logged without propagating.

    Concurrency: a SELECT FOR UPDATE on the parent Audit row serialises
    concurrent _persist_traces calls for the same audit_id, preventing
    chain forks where two batches both claim the same prev_hash.
    """
    traces = engine.get_traces()
    findings = engine.get_sample_findings()
    if not traces and not findings:
        return

    # Lock the parent audit row to serialise concurrent writes for this audit,
    # and read its tenant_id so each trace inherits it (FND-013: traces must carry
    # tenant_id for RLS — NULL rows are invisible under tenant_isolation_audit_traces).
    parent_audit = db.execute(
        _sql_text("SELECT tenant_id FROM audits WHERE id = :aid FOR UPDATE"),
        {"aid": str(audit_id)},
    ).first()
    parent_tenant_id = parent_audit[0] if parent_audit else None

    # Seed prev_hash from the last chain-enabled event for this audit.
    last = (
        db.query(AuditTrace.event_hash)
        .filter(
            AuditTrace.audit_id == audit_id,
            AuditTrace.event_hash != LEGACY_SENTINEL,
        )
        .order_by(AuditTrace.created_at.desc(), AuditTrace.id.desc())
        .first()
    )
    prev_hash: str | None = last[0] if last else None

    for t in traces:
        event_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc)
        event_data = {
            "id": str(event_id),
            "audit_id": str(audit_id),
            "gate_id": str(t["gate_id"]),
            "gate_name": str(t.get("gate_name") or ""),
            "check_type": str(t.get("check_type") or ""),
            "check_name": str(t.get("check_name") or ""),
            "result": str(t["result"]),
            "reason": str(t.get("reason") or ""),
            "signal_text": str(t.get("signal_text") or ""),
            "remediation_hint": str(t.get("remediation_hint") or ""),
            "created_at": created_at.isoformat(),
        }
        event_hash = compute_event_hash(event_data, prev_hash)

        db.add(AuditTrace(
            id=event_id,
            created_at=created_at,
            audit_id=audit_id,
            tenant_id=parent_tenant_id,
            gate_id=t["gate_id"],
            gate_name=t["gate_name"],
            check_type=t["check_type"],
            check_name=t["check_name"],
            result=t["result"],
            reason=t.get("reason"),
            detail_json=t.get("detail_json"),
            remediation_hint=t.get("remediation_hint"),
            signal_text=t.get("signal_text"),
            top_sample_ids=t.get("top_sample_ids"),
            event_hash=event_hash,
            prev_hash=prev_hash,
        ))
        prev_hash = event_hash

    # Sample findings are non-critical — failures are logged but not propagated.
    # PT-002: dedupe at the signal level — one row per (sample_id, domain,
    # matched_signal). Identical re-matches collapse; distinct samples are kept.
    try:
        deduped = _dedupe_findings(findings)
        db.bulk_save_objects([
            SampleFinding(
                audit_id=audit_id,
                sample_id=f["sample_id"],
                domain=f["domain"],
                matched_signal=f["matched_signal"],
                matched_text_fragment=f.get("matched_text_fragment"),
                weight=f["weight"],
            )
            for f in deduped
        ])
    except Exception as finding_exc:
        logger.warning(
            "Could not persist sample findings for audit %s: %s", audit_id, finding_exc
        )
        db.rollback()
        return

    db.commit()
    logger.info(
        "Persisted %d trace records and %d sample findings (%d after signal-level dedupe) for audit %s",
        len(traces), len(findings), len(deduped), audit_id,
    )


@router.post(
    "/scan",
    response_model=AuditReportOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Submit a batch for full SARO audit",
    description=(
        "Accepts a JSON batch of ≥50 text samples, runs the 4-gate audit pipeline, "
        "and returns the complete report including MIT coverage, similar incidents, "
        "fixed-delta, Bayesian risk scores, applied rules, and remediations.\n\n"
        "**Minimum 50 samples required** (internal SARO statistical methodology — "
        "see the Sampling Methodology Basis in the Compliance Claims Matrix)."
    ),
)
def scan_batch(
    payload: BatchIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditReportOut:
    """
    Full inline batch scan.

    The engine is instantiated per-request so the reference DB data is always
    fresh.  For high-throughput deployments, cache the engine at the app level
    after confirming reference data is stable.
    """
    audit_id = uuid.uuid4()

    # Persist the audit record immediately (status=running)
    audit = Audit(
        id=audit_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        batch_id=payload.batch_id,
        dataset_name=payload.dataset_name,
        sample_count=len(payload.samples),
        status="running",
    )
    db.add(audit)
    db.commit()

    try:
        engine = SARoEngine(db)
        report: AuditReportOut = engine.run_audit(payload, audit_id)

        # Persist the report
        scan_report = ScanReport(
            audit_id=audit_id,
            tenant_id=current_user.tenant_id,
            mit_coverage_score=report.mit_coverage.score,
            fixed_delta=report.fixed_delta.delta,
            overall_risk_score=report.bayesian_scores.overall,
            confidence_score=report.confidence_score,
            report_json=report.model_dump(mode="json"),
            # SARO-006: engine provenance
            engine_version=report.engine_version,
            rule_pack_hash=report.rule_pack_hash,
            compliance_matrix_version="v8.0.0",
        )
        db.add(scan_report)

        # Update audit status
        audit.status = report.status
        audit.completed_at = datetime.now(tz=timezone.utc)
        db.commit()

        # ── Persist audit traces (non-critical — never block the response) ──
        _persist_traces(engine, audit_id, db)

        # SAR-008: dispatch notification when risk score is high or critical
        _maybe_dispatch_risk_notification(
            db=db,
            tenant_id=current_user.tenant_id,
            audit_id=audit_id,
            overall_risk=report.bayesian_scores.overall,
            dataset_name=payload.dataset_name or "Unnamed dataset",
        )

        logger.info(
            "Audit %s completed: status=%s, mit_coverage=%.3f, delta=%.3f",
            audit_id,
            report.status,
            report.mit_coverage.score,
            report.fixed_delta.delta,
        )
        return report

    except Exception as exc:
        # Roll back any aborted transaction before attempting a status update.
        # Without this, a failed reference-table query (InFailedSqlTransaction)
        # will cause the commit below to fail as well, hiding the real error.
        try:
            db.rollback()
            audit.status = "failed"
            audit.completed_at = datetime.now(tz=timezone.utc)
            db.commit()
        except Exception as inner:
            logger.warning("Could not persist audit failure status for %s: %s", audit_id, inner)
            db.rollback()
        logger.exception("Audit %s failed: %s", audit_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit engine error: {exc}",
        ) from exc


@router.get(
    "/audits",
    response_model=list[AuditListItemOut],
    dependencies=[Depends(_require_audits_list_read)],
    summary="List audits for the current tenant",
)
def list_audits(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditListItemOut]:
    rows = (
        db.query(Audit, ScanReport)
        .outerjoin(ScanReport, ScanReport.audit_id == Audit.id)
        .filter(Audit.tenant_id == current_user.tenant_id)
        .order_by(Audit.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    result: list[AuditListItemOut] = []
    for audit, report in rows:
        result.append(
            AuditListItemOut(
                id=audit.id,
                batch_id=audit.batch_id,
                dataset_name=audit.dataset_name,
                sample_count=audit.sample_count,
                status=audit.status,
                mit_coverage_score=report.mit_coverage_score if report else None,
                fixed_delta=report.fixed_delta if report else None,
                overall_risk_score=report.overall_risk_score if report else None,
                created_at=audit.created_at,
            )
        )
    return result


@router.get(
    "/audits/{audit_id}",
    response_model=AuditReportOut,
    dependencies=[Depends(_require_audit_detail_read)],
    summary="Fetch a specific audit report",
)
def get_audit(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditReportOut:
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    if not audit.report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not yet available"
        )
    # Deserialise from stored JSON
    return AuditReportOut.model_validate(audit.report.report_json)


# ─────────────────────────────────────────────────────────────────────────────
# /api/v1/scan/data  — saro_data framework endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/scan/data",
    response_model=AuditReportOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Submit a saro_data framework batch for full SARO audit",
    description=(
        "Accepts the saro_data framework batch format "
        "(`model_type` / `intended_use` / `model_outputs`) and routes it "
        "through the same 4-gate audit pipeline as POST /api/v1/scan.\n\n"
        "The `model_outputs` field maps to samples as:\n"
        "- `output` → `text`\n"
        "- `gender` / `ethnicity` → `group`\n"
        "- `ground_truth` → `label`\n\n"
        "**Minimum 50 samples required** (internal SARO statistical methodology — "
        "see the Sampling Methodology Basis in the Compliance Claims Matrix)."
    ),
)
def scan_data_batch(
    payload: SARoDataBatchIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditReportOut:
    """
    Translate saro_data framework format → BatchIn and run the full audit.

    This endpoint is the primary integration point for the saro_data CLI
    (saro-data run / saro-data upload).  It accepts the richer saro_data
    schema and transparently converts it so the same engine handles both
    the Streamlit Upload tab (samples format) and the CLI (model_outputs format).
    """
    # Translate saro_data format → standard BatchIn
    batch: BatchIn = payload.to_batch_in()

    audit_id = uuid.uuid4()
    audit = Audit(
        id=audit_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        batch_id=payload.batch_id,
        dataset_name=payload.model_type,
        sample_count=len(payload.model_outputs),
        status="running",
    )
    db.add(audit)
    db.commit()

    try:
        engine = SARoEngine(db)
        report: AuditReportOut = engine.run_audit(batch, audit_id)

        scan_report = ScanReport(
            audit_id=audit_id,
            tenant_id=current_user.tenant_id,
            mit_coverage_score=report.mit_coverage.score,
            fixed_delta=report.fixed_delta.delta,
            overall_risk_score=report.bayesian_scores.overall,
            confidence_score=report.confidence_score,
            report_json=report.model_dump(mode="json"),
        )
        db.add(scan_report)
        audit.status = report.status
        audit.completed_at = datetime.now(tz=timezone.utc)
        db.commit()

        # ── Persist audit traces (non-critical — never block the response) ──
        _persist_traces(engine, audit_id, db)

        logger.info(
            "saro_data audit %s completed: model_type=%s, samples=%d, "
            "mit_coverage=%.3f, delta=%.3f",
            audit_id,
            payload.model_type,
            len(payload.model_outputs),
            report.mit_coverage.score,
            report.fixed_delta.delta,
        )
        return report

    except Exception as exc:
        # Roll back any aborted transaction before attempting a status update.
        try:
            db.rollback()
            audit.status = "failed"
            audit.completed_at = datetime.now(tz=timezone.utc)
            db.commit()
        except Exception as inner:
            logger.warning(
                "Could not persist audit failure status for %s: %s", audit_id, inner
            )
            db.rollback()
        logger.exception("saro_data audit %s failed: %s", audit_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit engine error: {exc}",
        ) from exc
