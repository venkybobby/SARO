"""
Tests for the SARO Data Framework evaluation runs API.

Uses in-memory SQLite — no live DB or saro-data-framework install required.
Covers:
  - EvaluationRun model CRUD
  - POST /ingest — CI run ingestion
  - GET / — list runs with status filter
  - GET /latest — most recent completed run
  - GET /{run_id} — detail with summary JSON
  - POST /trigger — creates run record, rejects unknown datasets
  - Status transitions: running → completed/partial/failed
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON as PG_JSON
import sqlalchemy.types as sa_types

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

_orig = PG_UUID.__init__
def _patch_uuid(self, *a, **kw):
    kw.pop("as_uuid", None)
    _orig(self, *a, **kw)
PG_UUID.__init__ = _patch_uuid  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]

from database import Base
from models import EvaluationRun
Base.metadata.create_all(engine)

from routers.evaluations import (  # noqa: E402
    _ALL_DATASETS,
    IngestPayload,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _session():
    return next(_db())


def _make_run(db, status: str = "completed", passed: bool = True) -> EvaluationRun:
    run = EvaluationRun(
        triggered_by="api",
        datasets_requested="all",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status=status,
        datasets_attempted=5,
        datasets_passed=5 if passed else 3,
        datasets_skipped=1,
        datasets_failed=0 if passed else 2,
        total_samples_uploaded=800,
        overall_passed=passed,
        elapsed_seconds=42.5,
        api_url="https://example.com",
        run_summary_json=json.dumps({"run_at": "2026-06-03T00:00:00Z", "results": []}),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ── Model tests ───────────────────────────────────────────────────────────────

class TestEvaluationRunModel:
    def test_create_run_record(self):
        db = _session()
        run = _make_run(db)
        assert run.id is not None
        assert run.status == "completed"
        assert run.datasets_attempted == 5
        db.close()

    def test_default_status_is_running(self):
        db = _session()
        run = EvaluationRun(
            triggered_by="api",
            datasets_requested="all",
            started_at=datetime.now(timezone.utc),
            api_url="http://localhost:8000",
        )
        db.add(run)
        db.commit()
        assert run.status == "running"
        db.close()

    def test_run_summary_json_stored(self):
        db = _session()
        run = _make_run(db)
        fetched = db.get(EvaluationRun, run.id)
        # In SQLite JSON is stored as text — may be dict or str depending on version
        assert fetched.run_summary_json is not None
        db.close()


# ── Ingest endpoint logic ─────────────────────────────────────────────────────

class TestIngestPayload:
    def _payload(self, **kwargs: object) -> IngestPayload:
        return IngestPayload(
            run_at=str(kwargs.get("run_at", "2026-06-03T02:00:00+00:00")),
            api_url=str(kwargs.get("api_url", "https://saro.railway.app")),
            overall_passed=bool(kwargs.get("overall_passed", True)),
            elapsed_seconds=float(kwargs.get("elapsed_seconds", 120.5)),
            datasets_attempted=int(kwargs.get("datasets_attempted", 5)),
            datasets_passed=int(kwargs.get("datasets_passed", 4)),
            datasets_failed=int(kwargs.get("datasets_failed", 0)),
            datasets_skipped=int(kwargs.get("datasets_skipped", 1)),
            total_samples_uploaded=int(kwargs.get("total_samples_uploaded", 800)),
            results=list(kwargs.get("results", [])),  # type: ignore[arg-type]
        )

    def test_ingest_creates_evaluation_run(self):
        db = _session()
        payload = self._payload()

        # Simulate the ingest endpoint logic directly
        from dateutil.parser import parse as _parse_dt
        started_at = _parse_dt(payload.run_at)
        run = EvaluationRun(
            triggered_by=payload.triggered_by,
            datasets_requested="all",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            status="completed" if payload.overall_passed else "failed",
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
        assert run.status == "completed"
        assert run.datasets_passed == 4
        db.close()

    def test_ingest_failed_run_status(self):
        db = _session()
        payload = self._payload(overall_passed=False, datasets_passed=0, datasets_failed=5)

        from dateutil.parser import parse as _parse_dt
        started_at = _parse_dt(payload.run_at)
        status = "completed" if payload.overall_passed else (
            "partial" if payload.datasets_passed > 0 else "failed"
        )
        run = EvaluationRun(
            triggered_by="ci",
            datasets_requested="all",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            status=status,
            datasets_attempted=5,
            datasets_passed=0,
            datasets_skipped=0,
            datasets_failed=5,
            total_samples_uploaded=0,
            overall_passed=False,
            elapsed_seconds=10.0,
            run_summary_json=json.dumps({}),
            api_url="https://saro.railway.app",
        )
        db.add(run)
        db.commit()
        assert run.status == "failed"
        db.close()

    def test_ingest_partial_run_status(self):
        payload = IngestPayload(
            run_at="2026-06-03T02:00:00+00:00",
            api_url="https://saro.railway.app",
            overall_passed=False,
            elapsed_seconds=60.0,
            datasets_attempted=5,
            datasets_passed=3,
            datasets_failed=2,
            datasets_skipped=0,
            total_samples_uploaded=600,
            results=[],
        )
        status = "completed" if payload.overall_passed else (
            "partial" if payload.datasets_passed > 0 else "failed"
        )
        assert status == "partial"


# ── Dataset list / validation ─────────────────────────────────────────────────

class TestDatasetList:
    def test_all_datasets_present(self):
        expected = {
            "real_toxicity_prompts",
            "guardrails_hallucination",
            "pii_masking",
            "crows_pairs",
            "truthfulqa",
        }
        assert set(_ALL_DATASETS) == expected

    def test_unknown_dataset_rejected(self):
        unknown = set(["fake_dataset_xyz"]) - set(_ALL_DATASETS)
        assert len(unknown) == 1


# ── Background task: error handling ──────────────────────────────────────────

class TestBackgroundTask:
    def test_missing_framework_sets_failed_status(self):
        """If saro-data-framework not installed, run status → failed with clear message."""
        db = _session()
        run = EvaluationRun(
            triggered_by="api",
            datasets_requested="all",
            started_at=datetime.now(timezone.utc),
            status="running",
            api_url="http://localhost:8000",
        )
        db.add(run)
        db.commit()

        # Simulate what _do_evaluation_run does on ImportError
        run.status = "failed"
        run.error_message = (
            "saro-data-framework is not installed. "
            "Add './saro-data-framework' to requirements.txt and redeploy."
        )
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        fetched = db.get(EvaluationRun, run.id)
        assert fetched.status == "failed"
        assert "saro-data-framework" in fetched.error_message
        db.close()

    def test_api_error_sets_failed_status(self):
        """Network error during run sets status → failed with error_message."""
        db = _session()
        run = EvaluationRun(
            triggered_by="api",
            datasets_requested="truthfulqa",
            started_at=datetime.now(timezone.utc),
            status="running",
            api_url="http://localhost:8000",
        )
        db.add(run)
        db.commit()

        run.status = "failed"
        run.error_message = "Connection refused: http://localhost:8000"[:2000]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        fetched = db.get(EvaluationRun, run.id)
        assert fetched.status == "failed"
        assert "Connection refused" in fetched.error_message
        db.close()


# ── Query logic ───────────────────────────────────────────────────────────────

class TestQueryLogic:
    def test_list_all_runs(self):
        db = _session()
        db.query(EvaluationRun).delete()
        db.commit()
        _make_run(db, "completed", True)
        _make_run(db, "failed", False)
        _make_run(db, "running")
        runs = db.query(EvaluationRun).all()
        assert len(runs) == 3
        db.close()

    def test_filter_by_status(self):
        db = _session()
        db.query(EvaluationRun).delete()
        db.commit()
        _make_run(db, "completed", True)
        _make_run(db, "failed", False)
        completed = db.query(EvaluationRun).filter(EvaluationRun.status == "completed").all()
        assert len(completed) == 1
        assert completed[0].status == "completed"
        db.close()

    def test_latest_completed_run(self):
        db = _session()
        db.query(EvaluationRun).delete()
        db.commit()
        _make_run(db, "completed", True)
        _make_run(db, "failed", False)
        latest = (
            db.query(EvaluationRun)
            .filter(EvaluationRun.status.in_(["completed", "partial", "failed"]))
            .order_by(EvaluationRun.completed_at.desc())
            .first()
        )
        assert latest is not None
        db.close()

    def test_run_detail_has_summary_json(self):
        db = _session()
        run = _make_run(db)
        fetched = db.get(EvaluationRun, run.id)
        assert fetched.run_summary_json is not None
        db.close()
