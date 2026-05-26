"""
HuggingFace Sample Processor — S-003

Picks up 'pending' rows from hf_sample_queue and runs them through
the SARO engine, updating status to 'processed' or 'failed'.

POST /api/v1/hf/process         — trigger processing of pending samples
GET  /api/v1/hf/queue/status    — summary of queue counts by status
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from engine import SARoEngine
from models import (
    Audit,
    AuditMetadata,
    AuditTrace,
    HFSampleQueue,
    ScanReport,
    User,
)

log = structlog.get_logger(__name__)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hf", tags=["hf-processor"])

_BATCH_SIZE = 20  # rows processed per trigger call


# ── Background processor ──────────────────────────────────────────────────────


def _process_single_row(row: HFSampleQueue, db: Session) -> None:
    """
    Process one HFSampleQueue row synchronously.

    Creates an Audit, runs SARoEngine.run_output_audit, persists the
    ScanReport and traces, then marks the queue row as 'processed'.
    On any exception the row is marked 'failed' with error_message set.
    """
    audit_id = uuid.uuid4()
    try:
        # Create Audit record
        audit = Audit(
            id=audit_id,
            tenant_id=row.tenant_id,
            user_id=None,  # batch job — no user
            batch_id=None,
            dataset_name=f"HF:{row.source_dataset}",
            sample_count=1,
            status="running",
            prompt_text=row.prompt_text,
            raw_output_text=row.raw_output_text,
        )
        db.add(audit)

        meta = AuditMetadata(
            audit_id=audit_id,
            source_model=row.source_model,
            ingestion_method="batch_scan",
        )
        db.add(meta)
        db.commit()

        # Mark queue row as processing
        row.status = "processing"
        row.audit_id = audit_id
        row.updated_at = datetime.now(timezone.utc)
        db.commit()

        # Run engine
        engine_obj = SARoEngine(db)
        report = engine_obj.run_output_audit(
            audit_id=audit_id,
            raw_output=row.raw_output_text,
            prompt=row.prompt_text,
            source_model=row.source_model,
        )

        # Persist scan report
        scan_report = ScanReport(
            audit_id=audit_id,
            mit_coverage_score=report.mit_coverage.score,
            fixed_delta=report.fixed_delta.delta,
            overall_risk_score=report.bayesian_scores.overall,
            confidence_score=report.confidence_score,
            report_json={
                **report.model_dump(mode="json"),
                "source_model": row.source_model,
                "vertical": row.vertical,
                "source_dataset": row.source_dataset,
            },
        )
        db.add(scan_report)

        # Persist traces
        traces = engine_obj.get_traces()
        for t in (traces or []):
            db.add(AuditTrace(
                audit_id=audit_id,
                gate_id=t["gate_id"],
                gate_name=t["gate_name"],
                check_type=t["check_type"],
                check_name=t["check_name"],
                result=t["result"],
                reason=t.get("reason"),
                detail_json=t.get("detail_json"),
                remediation_hint=t.get("remediation_hint"),
            ))

        audit.status = report.status
        audit.completed_at = datetime.now(timezone.utc)

        row.status = "processed"
        row.processed_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        db.commit()

        log.info(
            "hf_processor: row processed",
            row_id=str(row.id),
            audit_id=str(audit_id),
            risk_score=report.bayesian_scores.overall,
        )

    except Exception as exc:
        db.rollback()
        try:
            row.status = "failed"
            row.error_message = str(exc)[:500]
            row.retry_count = (row.retry_count or 0) + 1
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()

        log.error(
            "hf_processor: row failed",
            row_id=str(row.id),
            error=str(exc),
        )


def _run_batch(tenant_id: uuid.UUID, batch_size: int, db: Session) -> dict[str, int]:
    """
    Pick up up to `batch_size` pending rows for the given tenant and process each.
    Returns a summary dict.
    """
    rows = (
        db.query(HFSampleQueue)
        .filter(
            HFSampleQueue.tenant_id == tenant_id,
            HFSampleQueue.status == "pending",
        )
        .order_by(HFSampleQueue.sampled_at)
        .limit(batch_size)
        .all()
    )

    processed = 0
    failed = 0
    for row in rows:
        _process_single_row(row, db)
        if row.status == "processed":
            processed += 1
        else:
            failed += 1

    return {"processed": processed, "failed": failed, "attempted": len(rows)}


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/process",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Process pending HuggingFace sample queue rows",
)
def trigger_hf_processing(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
    batch_size: int = _BATCH_SIZE,
) -> dict[str, Any]:
    """
    Trigger background processing of up to `batch_size` pending rows
    from the hf_sample_queue for the calling user's tenant.

    Processing runs synchronously in a background task.
    Returns immediately with a count of rows queued for processing.
    """
    pending_count = (
        db.query(HFSampleQueue)
        .filter(
            HFSampleQueue.tenant_id == current_user.tenant_id,
            HFSampleQueue.status == "pending",
        )
        .count()
    )

    if pending_count == 0:
        return {
            "status": "no_pending_rows",
            "pending_count": 0,
            "message": "No pending rows to process.",
        }

    tenant_id = current_user.tenant_id

    def _bg_task() -> None:
        from database import get_db as _get_db
        bg_db = next(_get_db())
        try:
            result = _run_batch(tenant_id, min(batch_size, _BATCH_SIZE), bg_db)
            log.info("hf_processor: background batch complete", **result)
        finally:
            bg_db.close()

    background_tasks.add_task(_bg_task)

    return {
        "status": "accepted",
        "pending_count": pending_count,
        "batch_size": min(batch_size, _BATCH_SIZE),
        "message": f"Processing up to {min(batch_size, _BATCH_SIZE)} rows in background.",
    }


@router.get(
    "/queue/status",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get HuggingFace sample queue status counts",
)
def get_queue_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Return counts of queue rows by status for the calling tenant."""
    from sqlalchemy import func

    counts = (
        db.query(HFSampleQueue.status, func.count(HFSampleQueue.id))
        .filter(HFSampleQueue.tenant_id == current_user.tenant_id)
        .group_by(HFSampleQueue.status)
        .all()
    )

    result: dict[str, int] = {
        "pending": 0,
        "processing": 0,
        "processed": 0,
        "failed": 0,
    }
    for status_val, cnt in counts:
        result[status_val] = cnt

    result["total"] = sum(result.values())
    return result
