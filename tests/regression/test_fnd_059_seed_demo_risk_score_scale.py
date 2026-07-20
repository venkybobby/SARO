"""FND-059: scripts/seed_demo.py stored overall_risk_score pre-multiplied by 100.

Every production writer (routers/scan.py, routers/ingest.py, routers/output_audit.py,
routers/hf_processor.py, services/audit_submission.py) persists
``ScanReport.overall_risk_score = report.bayesian_scores.overall`` — the engine's
0-1 probability (engine.py rounds ``overall_prob`` to 4 dp). The frontend scales
once for display (TraceView.jsx / ComplianceHub.jsx multiply by 100). seed_demo.py
was the lone outlier, storing ``overall * 100``, so seeded demo tenants rendered
"1286/100" risk chips (demo readiness review 2026-07-19, finding F1).

This test drives seed_demo's persistence helper with a stub engine and pins that
the stored value equals the engine's 0-1 probability, unscaled.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from database import Base  # noqa: E402
from models import Audit, ScanReport, Tenant, User  # noqa: E402
from scripts.seed_demo import _run_audit_and_persist  # noqa: E402

pytestmark = [pytest.mark.regression, pytest.mark.unit]

OVERALL_PROBABILITY = 0.1286  # engine-style 0-1 value; the bug stored 12.86


def _stub_engine_cls(overall: float):
    """Engine stand-in exposing exactly what _run_audit_and_persist reads."""
    report = MagicMock()
    report.bayesian_scores.overall = overall
    report.mit_coverage.score = 0.5
    report.fixed_delta.delta = 0.0
    report.confidence_score = 0.9
    report.model_dump_json.return_value = "{}"

    eng = MagicMock()
    eng.run_audit.return_value = report
    eng.get_traces.return_value = []
    return MagicMock(return_value=eng)


def test_seed_demo_stores_engine_probability_unscaled():
    db_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(db_engine)
    db = sessionmaker(bind=db_engine)()
    try:
        tenant = Tenant(name="FND-059", slug="fnd-059-demo")
        db.add(tenant)
        db.flush()
        user = User(
            email=f"fnd059-{uuid.uuid4().hex[:8]}@saro-demo.internal",
            hashed_password="x",
            role="operator",
            tenant_id=tenant.id,
        )
        db.add(user)
        db.flush()
        audit = Audit(
            tenant_id=tenant.id,
            user_id=user.id,
            dataset_name="FND-059 scale pin",
            sample_count=50,
            status="running",
        )
        db.add(audit)
        db.flush()

        samples = [{"text": f"sample {i}"} for i in range(50)]
        _run_audit_and_persist(
            db, _stub_engine_cls(OVERALL_PROBABILITY), audit, samples, "FND-059 scale pin"
        )

        stored = db.query(ScanReport).filter(ScanReport.audit_id == audit.id).one()
        assert stored.overall_risk_score == pytest.approx(OVERALL_PROBABILITY), (
            "seed_demo must persist the engine's 0-1 probability unscaled, like every "
            f"production writer — got {stored.overall_risk_score} "
            f"(x100 pre-scaling would be {OVERALL_PROBABILITY * 100})"
        )
        assert 0.0 <= stored.overall_risk_score <= 1.0
    finally:
        db.close()
