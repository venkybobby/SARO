"""
Universal AI Output Ingestion API — S-101 / S-102 / S-103

POST /api/v1/ingest              — ingest a single AI output for async audit
GET  /api/v1/audits/{audit_id}   — poll audit status
GET  /api/v1/sdk/snippet         — retrieve SDK integration code snippet
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from textwrap import dedent
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user, require_role, require_write_access
from database import get_db
from engine import SARoEngine
from models import Audit, AuditMetadata, AuditTrace, ScanReport, Tenant, User

log = structlog.get_logger(__name__)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingest"])

_SARO_API_URL = __import__("os").environ.get("SARO_API_URL", "http://localhost:8000").rstrip("/")

# ── S-101 Schemas ─────────────────────────────────────────────────────────────

_SOURCE_MODELS = Literal["grok", "claude", "openai", "sierra", "internal", "unknown"]

_VERTICALS = Literal[
    "healthcare", "finance", "legal", "hr", "customer_support",
    "education", "government", "retail", "general"
]


class IngestRequest(BaseModel):
    """Single AI output submission for async SARO risk audit."""

    prompt: str = Field(
        ..., min_length=1,
        description="The original prompt sent to the AI model (full text).",
    )
    raw_output: str = Field(
        ..., min_length=1,
        description="The raw AI-generated output to audit.",
    )
    source_model: _SOURCE_MODELS = Field(
        default="unknown",
        description="The AI model that produced this output.",
    )
    tenant_id: uuid.UUID = Field(
        ...,
        description="The tenant UUID this audit belongs to.",
    )
    vertical: _VERTICALS = Field(
        default="general",
        description="Business vertical for risk context.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller-supplied metadata (model_version, session_id, etc.).",
    )


class IngestResponse(BaseModel):
    """Immediate response from POST /api/v1/ingest."""
    audit_id: uuid.UUID
    status: str
    trace_url: str
    created_at: datetime


class AuditStatusResponse(BaseModel):
    """Response from GET /api/v1/audits/{audit_id}."""
    audit_id: uuid.UUID
    status: str
    risk_score: float | None = None
    mit_coverage_pct: float | None = None
    confidence_score: float | None = None
    exceptions_count: int | None = None
    trace_url: str
    created_at: datetime
    completed_at: datetime | None = None


# ── Background audit task ─────────────────────────────────────────────────────


def _run_audit_background(
    audit_id: uuid.UUID,
    prompt: str,
    raw_output: str,
    source_model: str,
) -> None:
    """
    Run the SARO engine for a single output in a background task.
    Opens its own DB session (background tasks run outside the request session).
    """
    from database import get_db as _get_db

    db = next(_get_db())
    try:
        audit = db.get(Audit, audit_id)
        if not audit:
            logger.warning("Background audit task: audit %s not found", audit_id)
            return

        engine_obj = SARoEngine(db)
        report = engine_obj.run_output_audit(
            audit_id=audit_id,
            raw_output=raw_output,
            prompt=prompt,
            source_model=source_model,
        )

        # Persist ScanReport
        scan_report = ScanReport(
            audit_id=audit_id,
            mit_coverage_score=report.mit_coverage.score,
            fixed_delta=report.fixed_delta.delta,
            overall_risk_score=report.bayesian_scores.overall,
            confidence_score=report.confidence_score,
            report_json={
                **report.model_dump(mode="json"),
                "source_model": source_model,
            },
        )
        db.add(scan_report)

        # Persist traces with SHA-256 hash chaining (AUD-001)
        from routers.scan import _persist_traces
        _persist_traces(engine_obj, audit_id, db)

        audit.status = report.status
        audit.completed_at = datetime.now(tz=timezone.utc)
        db.commit()

        log.info(
            "ingest: audit complete",
            audit_id=str(audit_id),
            risk_score=report.bayesian_scores.overall,
        )

    except Exception as exc:
        db.rollback()
        try:
            audit = db.get(Audit, audit_id)
            if audit:
                audit.status = "failed"
                audit.completed_at = datetime.now(tz=timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        log.error("ingest: audit failed", audit_id=str(audit_id), error=str(exc))
    finally:
        db.close()


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin", "operator")), Depends(require_write_access)],
    summary="Ingest a single AI output for asynchronous SARO audit",
    description=(
        "Submit any single AI-generated output for asynchronous risk, ethics, and "
        "governance assessment.\n\n"
        "**SARO never calls external models — you provide the raw output.**\n\n"
        "Returns immediately with `audit_id` and `trace_url`. Poll "
        "`GET /api/v1/audits/{audit_id}` for completion."
    ),
)
async def ingest_output(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IngestResponse:
    """
    Universal single-output ingestion.

    Validates tenant ownership, creates an Audit record, fires the engine
    as a background task, and returns a 201 immediately.
    """
    # Validate tenant exists and caller owns it
    tenant = db.get(Tenant, payload.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if current_user.tenant_id != payload.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="tenant_id in payload does not match authenticated user's tenant",
        )

    audit_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    audit = Audit(
        id=audit_id,
        tenant_id=payload.tenant_id,
        user_id=current_user.id,
        batch_id=None,
        dataset_name=f"Ingest:{payload.source_model}",
        sample_count=1,
        status="running",
        prompt_text=payload.prompt,
        raw_output_text=payload.raw_output,
        created_at=now,
    )
    db.add(audit)

    meta = AuditMetadata(
        audit_id=audit_id,
        source_model=payload.source_model,
        ingestion_method="api",
    )
    db.add(meta)
    db.commit()

    background_tasks.add_task(
        _run_audit_background,
        audit_id=audit_id,
        prompt=payload.prompt,
        raw_output=payload.raw_output,
        source_model=payload.source_model,
    )

    trace_url = f"{_SARO_API_URL}/api/v1/audit/{audit_id}/trace"

    log.info(
        "ingest: audit queued",
        audit_id=str(audit_id),
        source_model=payload.source_model,
        tenant_id=str(payload.tenant_id),
    )

    return IngestResponse(
        audit_id=audit_id,
        status="running",
        trace_url=trace_url,
        created_at=now,
    )


@router.get(
    "/ingest/{audit_id}",
    response_model=AuditStatusResponse,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Poll ingest audit status and results",
    description=(
        "Poll the status of an audit submitted via POST /api/v1/ingest. "
        "Returns immediately with current status. When status is 'completed', "
        "risk_score, mit_coverage_pct, confidence_score, and exceptions_count are populated."
    ),
)
async def get_audit_status(
    audit_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditStatusResponse:
    """
    Returns the current status of an audit created via POST /api/v1/ingest.

    When `status` is `completed`, the response includes risk_score,
    mit_coverage_pct, confidence_score, and exceptions_count.
    When `status` is `running`, these fields are null — poll again.
    """
    audit = db.get(Audit, audit_id)
    if not audit or audit.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Audit not found")

    trace_url = f"{_SARO_API_URL}/api/v1/audit/{audit_id}/trace"

    # Try to get metrics from the associated ScanReport
    report = db.query(ScanReport).filter(ScanReport.audit_id == audit_id).first()

    exceptions_count: int | None = None
    if report and audit.status == "completed":
        failed_results = {"fail", "warn", "flagged", "triggered"}
        exceptions_count = (
            db.query(AuditTrace)
            .filter(
                AuditTrace.audit_id == audit_id,
                AuditTrace.result.in_(failed_results),
            )
            .count()
        )

    return AuditStatusResponse(
        audit_id=audit_id,
        status=audit.status,
        risk_score=report.overall_risk_score if report else None,
        mit_coverage_pct=(report.mit_coverage_score * 100) if report and report.mit_coverage_score is not None else None,
        confidence_score=report.confidence_score if report else None,
        exceptions_count=exceptions_count,
        trace_url=trace_url,
        created_at=audit.created_at,
        completed_at=audit.completed_at,
    )


@router.get(
    "/sdk/snippet",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get SDK integration code snippet",
    description="Returns a copy-paste Python code snippet for integrating SARO into your application.",
)
async def get_sdk_snippet(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Returns a Python code snippet for calling POST /api/v1/ingest
    from an application. Includes the caller's tenant_id pre-filled.
    """
    base_url = _SARO_API_URL
    tenant_id = str(current_user.tenant_id)

    snippet = dedent(f"""\
        import requests

        import os
        SARO_API_URL = "{base_url}"
        SARO_BEARER  = os.environ.get("SARO_TOKEN", "")  # export SARO_TOKEN=<jwt>
        TENANT_ID    = "{tenant_id}"

        def audit_ai_output(prompt: str, raw_output: str, source_model: str = "unknown") -> dict:
            \"\"\"Submit a single AI output to SARO for risk assessment.\"\"\"
            response = requests.post(
                f"{{SARO_API_URL}}/api/v1/ingest",
                headers={{
                    "Authorization": f"Bearer {{SARO_BEARER}}",
                    "Content-Type": "application/json",
                }},
                json={{
                    "prompt": prompt,
                    "raw_output": raw_output,
                    "source_model": source_model,
                    "tenant_id": TENANT_ID,
                    "vertical": "general",
                }},
            )
            response.raise_for_status()
            return response.json()  # contains audit_id and trace_url


        def poll_audit_status(audit_id: str) -> dict:
            \"\"\"Poll until the audit completes (status == 'completed' or 'failed').\"\"\"
            import time
            for _ in range(60):  # max 60 polls (~60 seconds)
                r = requests.get(
                    f"{{SARO_API_URL}}/api/v1/ingest/{{audit_id}}",
                    headers={{"Authorization": f"Bearer {{SARO_BEARER}}"}},
                )
                r.raise_for_status()
                data = r.json()
                if data["status"] in ("completed", "failed"):
                    return data
                time.sleep(1)
            raise TimeoutError("Audit did not complete in time")


        # Example usage:
        result = audit_ai_output(
            prompt="What is the recommended treatment for diabetes?",
            raw_output="<your-model-output-here>",
            source_model="claude",
        )
        print("Audit started:", result["audit_id"])
        final = poll_audit_status(result["audit_id"])
        print("Risk score:", final.get("risk_score"))
        print("Trace URL:", final["trace_url"])
    """)

    return {
        "language": "python",
        "version": "1.0",
        "description": (
            "Python snippet for integrating SARO single-output ingestion. "
            "Replace SARO_TOKEN with your JWT from POST /api/v1/auth/login."
        ),
        "snippet": snippet,
        "tenant_id": tenant_id,
        "endpoints": {
            "ingest": f"{base_url}/api/v1/ingest",
            "status": f"{base_url}/api/v1/audits/{{audit_id}}",
            "trace": f"{base_url}/api/v1/audit/{{audit_id}}/trace",
        },
    }
