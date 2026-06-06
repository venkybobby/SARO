"""
SAR-010: Seed the unified control library with 20+ pre-mapped cross-framework controls.

Idempotent — safe to re-run. Uses ON CONFLICT DO NOTHING on control_id.

Usage:
    python scripts/seed_control_library.py
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_control_library")

# ── Pre-mapped controls ────────────────────────────────────────────────────────
# Each entry: (control_id, title, description, control_type, frameworks[])
# frameworks: list of (framework_key, clause_reference)

_CONTROLS = [
    (
        "CTRL-RISK-001", "Risk Assessment",
        "Systematic identification and evaluation of AI risks before and during deployment.",
        "detective",
        [("ISO_42001", "Cl.6.1"), ("EU_AI_ACT", "Art.9"), ("AIGP", "Pr.4"), ("NIST_AI_RMF", "MAP-1.1")],
    ),
    (
        "CTRL-OVER-001", "Human Oversight",
        "Ensure meaningful human oversight of AI decisions and ability to intervene.",
        "preventive",
        [("ISO_42001", "Cl.8.4"), ("EU_AI_ACT", "Art.14"), ("AIGP", "Pr.6"), ("NIST_AI_RMF", "GOVERN-1.7")],
    ),
    (
        "CTRL-TRANS-001", "Transparency and Explainability",
        "Document AI system capabilities, limitations, and decision logic for users and regulators.",
        "detective",
        [("ISO_42001", "Cl.8.3"), ("EU_AI_ACT", "Art.13"), ("AIGP", "Pr.3")],
    ),
    (
        "CTRL-DATA-001", "Data Quality and Governance",
        "Ensure training and operational data meets quality, representativeness, and provenance standards.",
        "preventive",
        [("ISO_42001", "Annex A.6"), ("EU_AI_ACT", "Art.10")],
    ),
    (
        "CTRL-INC-001", "Incident Response and Reporting",
        "Establish and exercise incident response procedures for AI system failures and adverse events.",
        "corrective",
        [("ISO_42001", "Cl.10.1"), ("EU_AI_ACT", "Art.73")],
    ),
    (
        "CTRL-FAIR-001", "Fairness and Non-Discrimination",
        "Detect and mitigate discriminatory outputs across protected demographic groups.",
        "detective",
        [("ISO_42001", "Cl.6.1.2"), ("EU_AI_ACT", "Art.10"), ("AIGP", "Pr.5"), ("NIST_AI_RMF", "MAP-2.3")],
    ),
    (
        "CTRL-PRIV-001", "Privacy and Data Protection",
        "Implement privacy-by-design principles and minimise personal data use in AI systems.",
        "preventive",
        [("ISO_42001", "Annex A.6.2"), ("EU_AI_ACT", "Art.10"), ("AIGP", "Pr.3")],
    ),
    (
        "CTRL-ROB-001", "Robustness and Resilience",
        "Test AI systems for adversarial inputs, distributional shift, and performance degradation.",
        "detective",
        [("ISO_42001", "Cl.8.5"), ("EU_AI_ACT", "Art.15"), ("NIST_AI_RMF", "MEASURE-2.6")],
    ),
    (
        "CTRL-DOC-001", "AI System Documentation",
        "Maintain comprehensive technical documentation covering design, data, and validation.",
        "detective",
        [("ISO_42001", "Cl.7.5"), ("EU_AI_ACT", "Art.11"), ("NIST_AI_RMF", "GOVERN-1.2")],
    ),
    (
        "CTRL-ACC-001", "Accountability and Governance Structure",
        "Assign clear roles, responsibilities, and escalation paths for AI system oversight.",
        "preventive",
        [("ISO_42001", "Cl.5.3"), ("EU_AI_ACT", "Art.17"), ("AIGP", "Pr.7"), ("NIST_AI_RMF", "GOVERN-1.1")],
    ),
    (
        "CTRL-MON-001", "Continuous Monitoring",
        "Implement real-time and periodic monitoring of AI system performance and behaviour drift.",
        "detective",
        [("ISO_42001", "Cl.9.1"), ("EU_AI_ACT", "Art.9(2)"), ("NIST_AI_RMF", "MEASURE-2.5")],
    ),
    (
        "CTRL-AUD-001", "Audit Trail and Immutable Logging",
        "Maintain tamper-evident logs of AI decisions, inputs, and outputs for audit purposes.",
        "detective",
        [("ISO_42001", "Cl.9.1"), ("EU_AI_ACT", "Art.12"), ("AIGP", "Pr.7"), ("NIST_AI_RMF", "GOVERN-6.2")],
    ),
    (
        "CTRL-TEST-001", "Pre-Deployment Testing and Validation",
        "Conduct rigorous testing including accuracy, safety, and bias evaluation before deployment.",
        "preventive",
        [("ISO_42001", "Cl.8.6"), ("EU_AI_ACT", "Art.9"), ("NIST_AI_RMF", "MEASURE-2.1")],
    ),
    (
        "CTRL-VEND-001", "Third-Party and Vendor Risk Management",
        "Assess and manage risks from AI components, models, or services provided by third parties.",
        "detective",
        [("ISO_42001", "Cl.8.1"), ("EU_AI_ACT", "Art.28"), ("NIST_AI_RMF", "MAP-3.5")],
    ),
    (
        "CTRL-ACCESS-001", "Access Control and Authentication",
        "Restrict access to AI systems and governance tools to authorised personnel.",
        "preventive",
        [("ISO_42001", "Annex A.6.2"), ("EU_AI_ACT", "Art.9(2)"), ("AIGP", "Pr.6"), ("NIST_AI_RMF", "GOVERN-6.1")],
    ),
    (
        "CTRL-REM-001", "Remediation Tracking",
        "Track identified AI risks to documented, verified resolution with human sign-off.",
        "corrective",
        [("ISO_42001", "Cl.10.1"), ("EU_AI_ACT", "Art.9(7)"), ("AIGP", "Pr.4"), ("NIST_AI_RMF", "RESPOND-1.1")],
    ),
    (
        "CTRL-SCOPE-001", "AI System Inventory and Classification",
        "Maintain a current inventory of all AI systems with risk classification and oversight assignment.",
        "detective",
        [("ISO_42001", "Cl.4.1"), ("EU_AI_ACT", "Art.49"), ("AIGP", "Pr.1"), ("NIST_AI_RMF", "MAP-1.1")],
    ),
    (
        "CTRL-COMP-001", "Regulatory Compliance Mapping",
        "Map AI system controls to applicable regulatory obligations and maintain evidence packages.",
        "detective",
        [("ISO_42001", "Cl.6.1.3"), ("EU_AI_ACT", "Art.9"), ("AIGP", "Pr.7"), ("NIST_AI_RMF", "GOVERN-5.2")],
    ),
    (
        "CTRL-DRIFT-001", "Drift Detection and Alerting",
        "Detect statistical drift in model outputs against baseline distributions and alert stakeholders.",
        "detective",
        [("ISO_42001", "Cl.9.1"), ("NIST_AI_RMF", "MEASURE-2.5")],
    ),
    (
        "CTRL-NOTIF-001", "Risk Threshold Notification",
        "Automatically notify responsible parties when risk scores breach defined thresholds.",
        "detective",
        [("ISO_42001", "Cl.8.3"), ("EU_AI_ACT", "Art.9(6)"), ("AIGP", "Pr.5"), ("NIST_AI_RMF", "RESPOND-1.1")],
    ),
    (
        "CTRL-BIAS-001", "Bias Assessment and Mitigation",
        "Measure and reduce bias in AI training data, model outputs, and decision pipelines.",
        "detective",
        [("ISO_42001", "Cl.6.1.2"), ("EU_AI_ACT", "Art.10"), ("AIGP", "Pr.5"), ("NIST_AI_RMF", "MAP-2.3")],
    ),
    (
        "CTRL-RETRAIN-001", "Model Retraining and Version Control",
        "Establish versioned retraining cadences with regression testing and approval gates.",
        "preventive",
        [("ISO_42001", "Cl.8.6"), ("EU_AI_ACT", "Art.9"), ("NIST_AI_RMF", "MANAGE-3.1")],
    ),
]


def seed(db_url: str | None = None) -> int:
    """Seed the control library. Returns count of controls inserted."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    url = db_url or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL not set")

    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    db = Session()

    inserted = 0
    try:
        for ctrl_id, title, description, ctrl_type, frameworks in _CONTROLS:
            # Idempotent insert
            existing = db.execute(
                text("SELECT id FROM controls WHERE control_id = :cid"),
                {"cid": ctrl_id},
            ).fetchone()

            if existing:
                control_uuid = existing[0]
                logger.debug("Control %s already exists, skipping", ctrl_id)
            else:
                control_uuid = str(uuid.uuid4())
                db.execute(
                    text("""
                        INSERT INTO controls (id, control_id, title, description, control_type, status)
                        VALUES (:id, :control_id, :title, :description, :control_type, 'active')
                        ON CONFLICT (control_id) DO NOTHING
                    """),
                    {
                        "id": control_uuid,
                        "control_id": ctrl_id,
                        "title": title,
                        "description": description,
                        "control_type": ctrl_type,
                    },
                )
                inserted += 1
                logger.info("Inserted control: %s — %s", ctrl_id, title)

            # Seed framework mappings
            for framework, clause in frameworks:
                db.execute(
                    text("""
                        INSERT INTO control_framework_mappings (id, control_id, framework, clause_reference)
                        SELECT :id, :control_id, :framework, :clause
                        WHERE NOT EXISTS (
                            SELECT 1 FROM control_framework_mappings
                            WHERE control_id = :control_id AND framework = :framework
                        )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "control_id": control_uuid,
                        "framework": framework,
                        "clause": clause,
                    },
                )

        db.commit()
        logger.info("Seed complete: %d controls inserted", inserted)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return inserted


if __name__ == "__main__":
    count = seed()
    print(f"Seed complete: {count} new controls inserted")
