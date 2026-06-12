"""
Universal AI Output Ingestion routes.

POST /api/v1/audit/output        — audit any single AI-generated output
GET  /api/v1/audit/output/{id}   — retrieve result + full enhanced trace

SARO never calls external models — the caller provides the raw output.
Accepts outputs from Grok, Claude, OpenAI, Sierra, internal models, or any source.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db
from engine import SARoEngine
from models import Audit, AuditMetadata, AuditTrace, EnhancedTrace, ScanReport, User
from routers.dashboard import _synthesize_cot, _generate_executive_summary, _build_output_summary
from schemas import (
    AuditReportOut,
    EnhancedTraceOut,
    SingleOutputAuditIn,
    SingleOutputAuditOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/audit", tags=["output-audit"])

_AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", "")
_SARO_API_URL = os.environ.get("SARO_API_URL", "http://localhost:8000").rstrip("/")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _store_text_field(text: str, s3_prefix: str) -> tuple[str | None, str | None]:
    """
    Store a large text field.

    Returns (db_text, s3_key).
    If AWS_S3_BUCKET is set and text exceeds 50 KB, uploads to S3 and returns
    the object key.  Otherwise stores directly in the DB.
    """
    if _AWS_S3_BUCKET and len(text.encode("utf-8")) > 50_000:
        try:
            import boto3  # type: ignore[import]
            s3 = boto3.client("s3")
            key = f"traces/{s3_prefix}/{uuid.uuid4()}.txt"
            s3.put_object(
                Bucket=_AWS_S3_BUCKET,
                Key=key,
                Body=text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
            logger.info("Stored large text in S3: s3://%s/%s", _AWS_S3_BUCKET, key)
            return None, key
        except Exception as exc:
            logger.warning("S3 upload failed, falling back to DB storage: %s", exc)
    return text, None


def _persist_output_traces(engine: SARoEngine, audit_id: uuid.UUID, db: Session) -> None:
    """Persist traces from a single-output audit with SHA-256 hash chaining (AUD-001)."""
    from routers.scan import _persist_traces
    _persist_traces(engine, audit_id, db)


def _build_enhanced_trace(
    audit_id: uuid.UUID,
    prompt_text: str | None,
    raw_output_text: str | None,
    report: ScanReport,
    traces: list[AuditTrace],
    source_model: str,
    db: Session,
) -> EnhancedTrace:
    """Synthesise and persist the full enhanced trace for a single-output audit."""
    cot = _synthesize_cot(traces)
    exec_summary = _generate_executive_summary(report, traces)
    output_summary = _build_output_summary(report)

    input_summary: dict[str, Any] = {
        "ingestion_mode": "single_output",
        "source_model": source_model,
        "prompt_length_chars": len(prompt_text or ""),
        "output_length_chars": len(raw_output_text or ""),
        "note": "Full prompt and output text stored in prompt_text / raw_output_text fields.",
    }

    # Build the raw audit pipeline representation
    raw_prompt_desc = (
        f"SARO Universal Output Audit — Single-Output Mode\n"
        f"Source Model: {source_model}\n"
        f"Gates: Risk Classification (Gate 3) + Compliance Mapping (Gate 4)\n\n"
        f"--- ORIGINAL PROMPT ---\n{prompt_text or '[not provided]'}\n\n"
        f"--- RAW AI OUTPUT ---\n{raw_output_text or '[not provided]'}"
    )
    raw_response_desc = json.dumps(
        {"audit_id": str(audit_id), "chain_of_thought": cot, "report_summary": output_summary},
        indent=2, default=str,
    )

    # Export hash (SHA-256 of the full trace JSON)
    export_payload = json.dumps(
        {
            "audit_id": str(audit_id),
            "prompt_text": prompt_text,
            "raw_output_text": raw_output_text,
            "chain_of_thought": cot,
            "executive_summary": exec_summary,
            "source_model": source_model,
        },
        sort_keys=True, default=str,
    )
    export_hash = hashlib.sha256(export_payload.encode()).hexdigest()

    enhanced = EnhancedTrace(
        audit_id=audit_id,
        confidence=report.confidence_score,
        model_version="saro-engine-1.0",
        executive_summary=exec_summary,
        chain_of_thought=cot,
        client_input_summary=input_summary,
        client_output_summary=output_summary,
        raw_prompt=raw_prompt_desc,
        raw_response=raw_response_desc,
        prompt_text=prompt_text,
        raw_output_text=raw_output_text,
        export_hash=export_hash,
    )
    db.add(enhanced)
    db.commit()
    db.refresh(enhanced)
    return enhanced


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/output",
    response_model=SingleOutputAuditOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Audit any single AI-generated output — model-agnostic",
    description=(
        "Feed any AI output for instant risk/ethics/governance assessment.\n\n"
        "**SARO never calls external models — you provide the output.**\n\n"
        "Accepts raw outputs from Grok, Claude, OpenAI, Sierra, internal LLMs, or any source. "
        "Runs Gates 3 (Risk Classification) and 4 (Compliance Mapping) from the SARO pipeline, "
        "returning a full trace with zero truncation."
    ),
)
def audit_single_output(
    payload: SingleOutputAuditIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SingleOutputAuditOut:
    """
    Universal AI output ingestion.

    Creates an Audit record, runs the single-output pipeline (Gates 3+4),
    persists the report, synthesises a full enhanced trace, and returns the
    complete result immediately.
    """
    audit_id = uuid.uuid4()

    # Handle large text storage (S3 or DB)
    prompt_db, prompt_s3 = _store_text_field(payload.prompt, f"{audit_id}/prompt")
    output_db, output_s3 = _store_text_field(payload.raw_output, f"{audit_id}/output")

    # Persist Audit record
    audit = Audit(
        id=audit_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        batch_id=None,
        dataset_name=f"Single Output ({payload.source_model})",
        sample_count=1,
        status="running",
    )
    db.add(audit)

    # Persist AuditMetadata
    meta = AuditMetadata(
        audit_id=audit_id,
        source_model=payload.source_model,
        ingestion_method=payload.ingestion_method,
        prompt_s3_key=prompt_s3,
        output_s3_key=output_s3,
    )
    db.add(meta)
    db.commit()

    try:
        engine = SARoEngine(db)
        report: AuditReportOut = engine.run_output_audit(
            audit_id=audit_id,
            raw_output=payload.raw_output,
            prompt=payload.prompt,
            source_model=payload.source_model,
        )

        scan_report = ScanReport(
            audit_id=audit_id,
            tenant_id=current_user.tenant_id,
            mit_coverage_score=report.mit_coverage.score,
            fixed_delta=report.fixed_delta.delta,
            overall_risk_score=report.bayesian_scores.overall,
            confidence_score=report.confidence_score,
            report_json={
                **report.model_dump(mode="json"),
                "source_model": payload.source_model,
                "ingestion_method": payload.ingestion_method,
                "metadata": payload.metadata,
            },
        )
        db.add(scan_report)
        audit.status = report.status
        audit.completed_at = datetime.now(tz=timezone.utc)
        db.commit()

        # Persist traces
        _persist_output_traces(engine, audit_id, db)

        # Build and persist enhanced trace (with verbatim prompt + output)
        traces = (
            db.query(AuditTrace)
            .filter(AuditTrace.audit_id == audit_id)
            .order_by(AuditTrace.gate_id, AuditTrace.created_at)
            .all()
        )
        _build_enhanced_trace(
            audit_id=audit_id,
            prompt_text=prompt_db,
            raw_output_text=output_db,
            report=scan_report,
            traces=traces,
            source_model=payload.source_model,
            db=db,
        )

        # Count exceptions
        failed_results = {"fail", "warn", "flagged", "triggered"}
        exceptions = sum(1 for t in traces if t.result in failed_results)

        logger.info(
            "Output audit %s completed: model=%s, risk=%.2f, exceptions=%d",
            audit_id, payload.source_model,
            report.bayesian_scores.overall, exceptions,
        )

        return SingleOutputAuditOut(
            audit_id=audit_id,
            status=report.status,
            source_model=payload.source_model,
            ingestion_method=payload.ingestion_method,
            risk_score=report.bayesian_scores.overall,
            mit_coverage_pct=report.mit_coverage.score * 100,
            confidence_score=report.confidence_score,
            exceptions_count=exceptions,
            remediation_count=len(report.remediations),
            trace_endpoint=f"{_SARO_API_URL}/api/v1/dashboard/audits/{audit_id}/trace",
            report=report,
            created_at=audit.completed_at or datetime.now(tz=timezone.utc),
        )

    except Exception as exc:
        try:
            db.rollback()
            audit.status = "failed"
            audit.completed_at = datetime.now(tz=timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
        logger.exception("Output audit %s failed: %s", audit_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Output audit engine error: {exc}",
        ) from exc


@router.get(
    "/output/{audit_id}",
    response_model=EnhancedTraceOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Retrieve full enhanced trace for a single-output audit",
)
def get_output_audit_trace(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EnhancedTraceOut:
    """
    Returns the full, untruncated enhanced trace including verbatim
    prompt text and raw AI output.  Includes the export hash for
    cryptographic verification of the trace integrity.
    """
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")

    trace = db.query(EnhancedTrace).filter(EnhancedTrace.audit_id == audit_id).first()
    if not trace:
        raise HTTPException(
            status_code=404,
            detail="Enhanced trace not found. The audit may still be processing.",
        )
    return EnhancedTraceOut.model_validate(trace)
