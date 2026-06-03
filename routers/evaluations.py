"""
SARO Data Framework — Evaluation Runs API.

POST /api/v1/evaluations/trigger     — trigger a background evaluation run
GET  /api/v1/evaluations             — list evaluation runs (paginated)
GET  /api/v1/evaluations/{run_id}    — get full run details + per-dataset results
GET  /api/v1/evaluations/latest      — shortcut to most recent completed run
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from database import get_db, _get_session_factory
from models import EvaluationRun, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])

# ── Available datasets (matches REGISTRY in saro_data.converters) ─────────────
_ALL_DATASETS = [
    "real_toxicity_prompts",
    "guardrails_hallucination",
    "pii_masking",
    "crows_pairs",
    "truthfulqa",
]


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TriggerRequest(BaseModel):
    datasets: Optional[list[str]] = Field(
        default=None,
        description="Subset of datasets to run. Omit or pass null to run all enabled datasets.",
    )
    max_samples: Optional[int] = Field(
        default=200,
        ge=50,
        le=2000,
        description="Maximum samples per dataset (50–2000, default 200).",
    )


class EvaluationRunOut(BaseModel):
    id: uuid.UUID
    triggered_by: str
    triggered_by_user_id: Optional[uuid.UUID]
    datasets_requested: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    datasets_attempted: int
    datasets_passed: int
    datasets_skipped: int
    datasets_failed: int
    total_samples_uploaded: int
    overall_passed: Optional[bool]
    elapsed_seconds: Optional[float]
    api_url: str
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationRunDetailOut(EvaluationRunOut):
    run_summary_json: Optional[Any] = None  # parsed dict or raw string


# ── Background task ───────────────────────────────────────────────────────────

def _do_evaluation_run(run_id: uuid.UUID, datasets: list[str], max_samples: int) -> None:
    """
    Background task: instantiate TestRunner, execute the full pipeline,
    and persist results to the EvaluationRun row.

    Runs in a separate thread (BackgroundTasks), uses its own DB session.
    """
    db = _get_session_factory()()
    try:
        run = db.get(EvaluationRun, run_id)
        if run is None:
            logger.error("EvaluationRun %s not found — aborting background task", run_id)
            return

        api_url = os.environ.get("SARO_API_URL", "http://localhost:8000")
        token = os.environ.get("SARO_INTERNAL_TOKEN", "")
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

        run.api_url = api_url
        db.commit()

        try:
            # Import here so the main app starts even if saro-data-framework
            # is not installed (it will raise ImportError at trigger time only).
            from saro_data.runner import TestRunner  # type: ignore[import]
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                runner = TestRunner(
                    api_url=api_url,
                    token=token,
                    output_dir=Path(tmpdir),
                    datasets=datasets,
                    max_samples=max_samples,
                    hf_token=hf_token,
                )
                summary = runner.run()

            # Persist results
            run.completed_at = datetime.now(timezone.utc)
            run.datasets_attempted = summary.datasets_attempted
            run.datasets_passed = summary.datasets_passed
            run.datasets_skipped = summary.datasets_skipped
            run.datasets_failed = summary.datasets_failed
            run.total_samples_uploaded = summary.total_samples_uploaded
            run.overall_passed = summary.overall_passed
            run.elapsed_seconds = summary.elapsed_seconds
            run.run_summary_json = json.dumps(summary.as_dict())
            run.status = "completed" if summary.overall_passed else (
                "partial" if summary.datasets_passed > 0 else "failed"
            )

        except ImportError:
            run.status = "failed"
            run.error_message = (
                "saro-data-framework is not installed. "
                "Add './saro-data-framework' to requirements.txt and redeploy."
            )
            run.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.exception("EvaluationRun %s failed with unexpected error", run_id)
            run.status = "failed"
            run.error_message = str(exc)[:2000]
            run.completed_at = datetime.now(timezone.utc)

        db.commit()

    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/trigger",
    response_model=EvaluationRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Trigger a background evaluation run using all enabled datasets",
)
async def trigger_evaluation(
    body: TriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationRunOut:
    """
    Starts an asynchronous evaluation run. Returns immediately with the
    run record in status=running. Poll GET /api/v1/evaluations/{id} for results.

    Requires SARO_API_URL and SARO_INTERNAL_TOKEN env vars on the server.
    """
    datasets = body.datasets or _ALL_DATASETS
    unknown = set(datasets) - set(_ALL_DATASETS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown datasets: {sorted(unknown)}. Available: {_ALL_DATASETS}",
        )

    run = EvaluationRun(
        triggered_by="api",
        triggered_by_user_id=current_user.id,
        datasets_requested=",".join(datasets),
        started_at=datetime.now(timezone.utc),
        status="running",
        api_url=os.environ.get("SARO_API_URL", "http://localhost:8000"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(
        _do_evaluation_run,
        run_id=run.id,
        datasets=datasets,
        max_samples=body.max_samples or 200,
    )

    logger.info(
        "Evaluation run %s triggered by user %s — datasets: %s",
        run.id, current_user.id, datasets,
    )
    return EvaluationRunOut.model_validate(run)


@router.get(
    "/latest",
    response_model=EvaluationRunDetailOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get the most recently completed evaluation run",
)
def get_latest_evaluation(db: Session = Depends(get_db)) -> EvaluationRunDetailOut:
    run = (
        db.query(EvaluationRun)
        .filter(EvaluationRun.status.in_(["completed", "partial", "failed"]))
        .order_by(EvaluationRun.completed_at.desc())
        .first()
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed evaluation runs found.",
        )
    return EvaluationRunDetailOut.model_validate(run)


@router.get(
    "",
    response_model=list[EvaluationRunOut],
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="List evaluation runs (most recent first)",
)
def list_evaluations(
    status_filter: Optional[str] = Query(
        None, alias="status",
        description="Filter by status: running | completed | partial | failed"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[EvaluationRunOut]:
    q = db.query(EvaluationRun).order_by(EvaluationRun.started_at.desc())
    if status_filter:
        q = q.filter(EvaluationRun.status == status_filter)
    runs = q.limit(limit).offset(offset).all()
    return [EvaluationRunOut.model_validate(r) for r in runs]


@router.get(
    "/{run_id}",
    response_model=EvaluationRunDetailOut,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get full evaluation run details including per-dataset results",
)
def get_evaluation(run_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluationRunDetailOut:
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {run_id} not found.",
        )
    out = EvaluationRunDetailOut.model_validate(run)
    # Deserialise JSON text → dict for the API response
    if isinstance(out.run_summary_json, str):
        try:
            out.run_summary_json = json.loads(out.run_summary_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return out


# ── CI ingest endpoint ────────────────────────────────────────────────────────

class IngestPayload(BaseModel):
    """run_report.json payload posted by the GitHub Actions eval-weekly workflow."""
    run_at: str
    api_url: str
    overall_passed: bool
    elapsed_seconds: float
    datasets_attempted: int
    datasets_passed: int
    datasets_failed: int
    datasets_skipped: int = 0
    total_samples_uploaded: int
    results: list[Any] = Field(default_factory=list)
    triggered_by: str = "ci"
    workflow_run_url: Optional[str] = None


@router.post(
    "/ingest",
    response_model=EvaluationRunOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("super_admin"))],
    summary="Ingest a run_report.json posted by the CI evaluation workflow",
)
def ingest_evaluation(
    payload: IngestPayload,
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationRunOut:
    """
    Called by the eval-weekly GitHub Actions workflow after each evaluation run.
    Creates an EvaluationRun record from the CLI run_report.json output.
    """
    from dateutil.parser import parse as _parse_dt  # type: ignore[import]

    try:
        started_at = _parse_dt(payload.run_at)
    except Exception:
        started_at = datetime.now(timezone.utc)

    run = EvaluationRun(
        triggered_by=payload.triggered_by,
        triggered_by_user_id=None,
        datasets_requested="all",
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        status="completed" if payload.overall_passed else (
            "partial" if payload.datasets_passed > 0 else "failed"
        ),
        datasets_attempted=payload.datasets_attempted,
        datasets_passed=payload.datasets_passed,
        datasets_skipped=payload.datasets_skipped,
        datasets_failed=payload.datasets_failed,
        total_samples_uploaded=payload.total_samples_uploaded,
        overall_passed=payload.overall_passed,
        elapsed_seconds=payload.elapsed_seconds,
        run_summary_json=json.dumps(payload.model_dump()),
        api_url=payload.api_url,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info(
        "Evaluation run ingested from CI: id=%s status=%s passed=%s/%s",
        run.id, run.status, run.datasets_passed, run.datasets_attempted,
    )
    return EvaluationRunOut.model_validate(run)
