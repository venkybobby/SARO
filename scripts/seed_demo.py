"""
CF-03: Demo Data Seeder — Finance + Healthcare
================================================
Idempotent seed script. Creates demo tenant + compliance_lead user + pre-run
audit batches for Finance and Healthcare verticals.

Usage:
    python scripts/seed_demo.py

Or set SEED_DEMO_DATA=true in environment to run automatically on startup
(triggered from main.py lifespan if the env var is set).

Requires: DATABASE_URL env var (or .env file in repo root).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env if present (local dev)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo")

DEMO_TENANT_SLUG = "saro-demo"
DEMO_USER_EMAIL = "demo@saro-demo.internal"
DEMO_USER_PASSWORD = "SaroDemo2026!"  # never used in production
DEMO_DATA_DIR = ROOT / "demo_data"

_PERSONA_SEEDS = [
    {
        "persona_role": "compliance_lead",
        "allowed_tabs": ["dashboard", "audit", "trace", "remediate", "aims", "governance"],
        "allowed_actions": ["create_aims_document", "link_audit", "export_pdf", "view_trace"],
    },
    {
        "persona_role": "risk_officer",
        "allowed_tabs": ["dashboard", "trace", "notifications"],
        "allowed_actions": ["view_trace", "view_dashboard"],
    },
    {
        "persona_role": "ai_auditor",
        "allowed_tabs": ["dashboard", "audit", "trace", "rule_packs", "remediate"],
        "allowed_actions": ["view_trace", "view_rule_packs", "remediate_trace"],
    },
]


def _run_audit_and_persist(
    db,
    engine_cls,
    audit_obj,
    samples_data: list[dict],
    dataset_name: str,
) -> None:
    """Run audit engine on demo samples and persist traces + report."""
    from engine import SARoEngine
    from models import AuditTrace, ScanReport
    from schemas import BatchIn, SampleIn

    samples = [SampleIn(**s) for s in samples_data]
    batch = BatchIn(dataset_name=dataset_name, samples=samples)

    eng = engine_cls(db)
    report = eng.run_audit(batch, audit_obj.id)

    # Persist ScanReport
    overall_risk = report.bayesian_scores.overall * 100
    db.add(ScanReport(
        audit_id=audit_obj.id,
        mit_coverage_score=report.mit_coverage.score,
        fixed_delta=report.fixed_delta.delta,
        overall_risk_score=round(overall_risk, 2),
        confidence_score=report.confidence_score,
        report_json=json.loads(report.model_dump_json()),
    ))

    # Persist AuditTraces
    for trace in eng.get_traces():
        db.add(AuditTrace(
            audit_id=audit_obj.id,
            gate_id=trace["gate_id"],
            gate_name=trace["gate_name"],
            check_type=trace["check_type"],
            check_name=trace["check_name"],
            result=trace["result"],
            reason=trace.get("reason"),
            detail_json=trace.get("detail_json"),
            remediation_hint=trace.get("remediation_hint"),
        ))

    audit_obj.status = "completed"
    audit_obj.completed_at = datetime.now(tz=timezone.utc)
    db.commit()
    logger.info("Completed audit: %s (risk=%.1f)", dataset_name, overall_risk)


def seed() -> None:
    from auth import hash_password
    from database import create_all_tables, get_db, seed_persona_permissions
    from models import Audit, PersonaPermission, Tenant, User

    create_all_tables()
    seed_persona_permissions()

    db = next(get_db())
    try:
        # Idempotency check — skip if demo tenant exists
        tenant = db.query(Tenant).filter(Tenant.slug == DEMO_TENANT_SLUG).first()
        if tenant:
            logger.info("Demo tenant already exists (slug=%s) — skipping seed", DEMO_TENANT_SLUG)
            return

        # Create demo tenant
        tenant = Tenant(name="SARO Demo", slug=DEMO_TENANT_SLUG)
        db.add(tenant)
        db.flush()

        # Create compliance_lead demo user
        user = User(
            email=DEMO_USER_EMAIL,
            hashed_password=hash_password(DEMO_USER_PASSWORD),
            role="operator",
            persona_role="compliance_lead",
            tenant_id=tenant.id,
        )
        db.add(user)
        db.flush()
        logger.info("Created demo user: %s (persona=compliance_lead)", DEMO_USER_EMAIL)

        # Seed Finance audit
        finance_path = DEMO_DATA_DIR / "finance_demo.json"
        if finance_path.exists():
            finance_data = json.loads(finance_path.read_text())
            finance_audit = Audit(
                tenant_id=tenant.id,
                user_id=user.id,
                dataset_name=finance_data["dataset_name"],
                sample_count=len(finance_data["samples"]),
                status="running",
            )
            db.add(finance_audit)
            db.flush()
            from engine import SARoEngine
            _run_audit_and_persist(db, SARoEngine, finance_audit, finance_data["samples"], finance_data["dataset_name"])

        # Seed Healthcare audit
        health_path = DEMO_DATA_DIR / "healthcare_demo.json"
        if health_path.exists():
            health_data = json.loads(health_path.read_text())
            health_audit = Audit(
                tenant_id=tenant.id,
                user_id=user.id,
                dataset_name=health_data["dataset_name"],
                sample_count=len(health_data["samples"]),
                status="running",
            )
            db.add(health_audit)
            db.flush()
            from engine import SARoEngine
            _run_audit_and_persist(db, SARoEngine, health_audit, health_data["samples"], health_data["dataset_name"])

        db.commit()
        logger.info("Demo data seeding complete")

    except Exception:
        db.rollback()
        logger.exception("Demo data seeding failed")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
