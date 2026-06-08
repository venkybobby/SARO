"""
Cross-functional story integration tests — CF-01, CF-03, CF-04, CF-05, CF-06.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── CF-03 Demo data integrity tests ──────────────────────────────────────────


def test_finance_demo_sample_count():
    path = ROOT / "demo_data" / "finance_demo.json"
    assert path.exists(), "finance_demo.json not found"
    data = json.loads(path.read_text())
    assert len(data["samples"]) >= 60  # SAR-003: expanded to 200+ for demo stability


def test_finance_demo_no_nulls():
    path = ROOT / "demo_data" / "finance_demo.json"
    data = json.loads(path.read_text())
    for s in data["samples"]:
        assert s["text"] and s["text"].strip(), f"Blank text in sample {s['sample_id']}"
        assert len(s["text"].split()) >= 3, f"Too short text in sample {s['sample_id']}"


def test_healthcare_demo_sample_count():
    path = ROOT / "demo_data" / "healthcare_demo.json"
    assert path.exists(), "healthcare_demo.json not found"
    data = json.loads(path.read_text())
    assert len(data["samples"]) >= 60  # SAR-003: expanded to 200+ for demo stability


def test_healthcare_demo_no_nulls():
    path = ROOT / "demo_data" / "healthcare_demo.json"
    data = json.loads(path.read_text())
    for s in data["samples"]:
        assert s["text"] and s["text"].strip(), f"Blank text in sample {s['sample_id']}"


def test_finance_demo_domain_context_set():
    path = ROOT / "demo_data" / "finance_demo.json"
    data = json.loads(path.read_text())
    contexts = {s.get("domain_context") for s in data["samples"]}
    assert "finance" in contexts


def test_healthcare_demo_domain_context_set():
    path = ROOT / "demo_data" / "healthcare_demo.json"
    data = json.loads(path.read_text())
    contexts = {s.get("domain_context") for s in data["samples"]}
    assert "healthcare" in contexts


def test_finance_engine_gate3_triggers_privacy_and_discrimination():
    """Finance samples must trigger Privacy & Security and Discrimination domains (CF-03 AC-03)."""
    from engine import SARoEngine
    from rule_packs.loader import build_domain_trigger_map, load_all_packs
    from schemas import AuditConfigIn, BatchIn, SampleIn

    path = ROOT / "demo_data" / "finance_demo.json"
    data = json.loads(path.read_text())
    samples = [SampleIn(**s) for s in data["samples"]]

    eng = SARoEngine.__new__(SARoEngine)
    eng._mit_risks = []
    eng._incidents = []
    eng._eu_rules = []
    eng._nist_controls = []
    eng._aigp = []
    eng._gov_rules = []
    eng._tfidf_vectorizer = None
    eng._incident_matrix = None
    eng._rule_packs = load_all_packs(ROOT / "rule_packs")
    eng._compliance_triggers = build_domain_trigger_map(eng._rule_packs)

    cfg = AuditConfigIn.model_construct(min_samples=50, confidence_threshold=0.95, incident_top_k=0, frameworks=[])
    batch = BatchIn.model_construct(batch_id=None, dataset_name="finance", samples=samples, config=cfg)
    flags, gate3 = eng._gate3_risk_classification(batch)

    domain_counts = gate3.details["domain_flag_counts"]
    assert domain_counts.get("Privacy & Security", 0) >= 3, "Privacy & Security needs >= 3 flags"
    assert domain_counts.get("Discrimination & Toxicity", 0) >= 3, "Discrimination & Toxicity needs >= 3 flags"


def test_healthcare_engine_gate3_triggers_misinformation_and_privacy():
    """Healthcare samples must trigger Misinformation and Privacy domains (CF-03 AC-04)."""
    from engine import SARoEngine
    from rule_packs.loader import build_domain_trigger_map, load_all_packs
    from schemas import AuditConfigIn, BatchIn, SampleIn

    path = ROOT / "demo_data" / "healthcare_demo.json"
    data = json.loads(path.read_text())
    samples = [SampleIn(**s) for s in data["samples"]]

    eng = SARoEngine.__new__(SARoEngine)
    eng._mit_risks = []
    eng._incidents = []
    eng._eu_rules = []
    eng._nist_controls = []
    eng._aigp = []
    eng._gov_rules = []
    eng._tfidf_vectorizer = None
    eng._incident_matrix = None
    eng._rule_packs = load_all_packs(ROOT / "rule_packs")
    eng._compliance_triggers = build_domain_trigger_map(eng._rule_packs)

    cfg = AuditConfigIn.model_construct(min_samples=50, confidence_threshold=0.95, incident_top_k=0, frameworks=[])
    batch = BatchIn.model_construct(batch_id=None, dataset_name="healthcare", samples=samples, config=cfg)
    flags, gate3 = eng._gate3_risk_classification(batch)

    domain_counts = gate3.details["domain_flag_counts"]
    assert domain_counts.get("Misinformation", 0) >= 3, "Misinformation needs >= 3 flags"
    assert domain_counts.get("Privacy & Security", 0) >= 3, "Privacy & Security needs >= 3 flags"


def test_finance_gate4_triggers_all_three_frameworks():
    """Finance audit gate4 must trigger EU AI Act, NIST, and AIGP (CF-03 AC-05)."""
    from engine import SARoEngine
    from rule_packs.loader import build_domain_trigger_map, load_all_packs
    from schemas import AuditConfigIn, BatchIn, SampleIn

    path = ROOT / "demo_data" / "finance_demo.json"
    data = json.loads(path.read_text())
    samples = [SampleIn(**s) for s in data["samples"]]

    eng = SARoEngine.__new__(SARoEngine)
    eng._mit_risks = []
    eng._incidents = []
    eng._eu_rules = []
    eng._nist_controls = []
    eng._aigp = []
    eng._gov_rules = []
    eng._tfidf_vectorizer = None
    eng._incident_matrix = None
    eng._rule_packs = load_all_packs(ROOT / "rule_packs")
    eng._compliance_triggers = build_domain_trigger_map(eng._rule_packs)

    cfg = AuditConfigIn.model_construct(min_samples=50, confidence_threshold=0.95, incident_top_k=0, frameworks=[])
    batch = BatchIn.model_construct(batch_id=None, dataset_name="finance", samples=samples, config=cfg)
    flags, _ = eng._gate3_risk_classification(batch)
    eng._applied_rule_packs = {}
    applied_rules, _ = eng._gate4_compliance_mapping(flags)

    frameworks = {r.framework for r in applied_rules}
    assert "EU AI Act" in frameworks, "EU AI Act not in applied_rules"
    assert "NIST AI RMF" in frameworks, "NIST AI RMF not in applied_rules"
    assert "AIGP" in frameworks, "AIGP not in applied_rules"


# ── CF-01 Trace Export tests ──────────────────────────────────────────────────


def test_executive_steps_builder():
    from routers.trace_export import _build_executive_steps
    from models import AuditTrace

    trace = AuditTrace(
        id=uuid.uuid4(),
        audit_id=uuid.uuid4(),
        gate_id=3,
        gate_name="Risk Classification (MIT Taxonomy)",
        check_type="risk_domain",
        check_name="Privacy & Security",
        result="flagged",
        reason="PII detected in 5 samples",
        detail_json={},
        created_at=datetime.now(tz=timezone.utc),
        is_remediated=False,
    )
    steps = _build_executive_steps([trace])
    assert len(steps) == 1
    assert steps[0].severity == "High"
    assert "Privacy" in steps[0].finding or "PII" in steps[0].finding


def test_sign_report_deterministic():
    from routers.trace_export import _sign_report

    report = {"audit_id": "test-123", "score": 74, "findings": ["a", "b"]}
    hash1 = _sign_report(report)
    hash2 = _sign_report(report)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex


def test_pdf_renders_bytes():
    from routers.trace_export import _render_pdf
    from schemas import ExecutiveStep

    audit = MagicMock()
    audit.id = uuid.uuid4()
    audit.dataset_name = "Test Dataset"
    audit.completed_at = datetime.now(tz=timezone.utc)

    exec_steps = [
        ExecutiveStep(label="Gate 3: Risk", finding="PII detected in 5 samples.", severity="High"),
        ExecutiveStep(label="Gate 4: Compliance", finding="EU AI Act ART_10_3 triggered.", severity="Medium"),
    ]
    report_json = {
        "executive_summary": "Audit complete with 2 findings.",
        "overall_risk_score": 62,
        "confidence_score": 0.87,
        "rule_pack_versions": ["eu-ai-act@1.0.0"],
    }
    pdf_bytes = _render_pdf(audit, exec_steps, report_json, "a" * 64)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:4] == b"%PDF"


# ── CF-04 AIMS schemas ────────────────────────────────────────────────────────


def test_aims_document_in_schema_valid():
    from schemas import AIMSDocumentIn

    doc = AIMSDocumentIn(
        title="SARO Data Processing Policy v1",
        version="1.0.0",
        owner_email="compliance@acme.com",
    )
    assert doc.title == "SARO Data Processing Policy v1"
    assert doc.version == "1.0.0"


def test_aims_evidence_pack_disclaimer():
    from schemas import AIMSDocumentOut, AIMSEvidencePackOut

    doc = AIMSDocumentOut(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="Policy",
        version="1.0.0",
        effective_date=None,
        owner_email="owner@acme.com",
        linked_audit_ids=[],
        created_at=datetime.now(tz=timezone.utc),
        updated_at=None,
    )
    pack = AIMSEvidencePackOut(document=doc, linked_audits=[], generated_at=datetime.now(tz=timezone.utc))
    assert "SARO v8.0.0" in pack.disclaimer
    assert "does not constitute" in pack.disclaimer


# ── CF-05 Governance doc existence ────────────────────────────────────────────


def test_nist_pdf_exists():
    p = ROOT / "docs" / "saro-nist-ai-rmf-self-assessment-v1.0.pdf"
    assert p.exists(), "NIST self-assessment PDF missing — run scripts/generate_governance_pdfs.py"
    assert p.stat().st_size > 1000


def test_eu_pdf_exists():
    p = ROOT / "docs" / "saro-eu-ai-act-position-v1.0.pdf"
    assert p.exists(), "EU AI Act position PDF missing — run scripts/generate_governance_pdfs.py"
    assert p.stat().st_size > 1000


def test_nist_pdf_starts_with_pdf_magic():
    p = ROOT / "docs" / "saro-nist-ai-rmf-self-assessment-v1.0.pdf"
    if p.exists():
        assert p.read_bytes()[:4] == b"%PDF"


# ── CF-06 PersonaPermission seeds ─────────────────────────────────────────────


def test_persona_permission_seeds_defined():
    from database import _PERSONA_SEEDS

    roles = {s["persona_role"] for s in _PERSONA_SEEDS}
    assert "compliance_lead" in roles
    assert "risk_officer" in roles
    assert "ai_auditor" in roles


def test_compliance_lead_tabs():
    from database import _PERSONA_SEEDS

    cl = next(s for s in _PERSONA_SEEDS if s["persona_role"] == "compliance_lead")
    assert "aims" in cl["allowed_tabs"]
    assert "governance" in cl["allowed_tabs"]
    assert "trace" in cl["allowed_tabs"]
    assert "create_aims_document" in cl["allowed_actions"]


def test_risk_officer_no_aims_tab():
    from database import _PERSONA_SEEDS

    ro = next(s for s in _PERSONA_SEEDS if s["persona_role"] == "risk_officer")
    assert "aims" not in ro["allowed_tabs"]
    assert "rule_packs" not in ro["allowed_tabs"]


def test_ai_auditor_has_rule_packs():
    from database import _PERSONA_SEEDS

    aa = next(s for s in _PERSONA_SEEDS if s["persona_role"] == "ai_auditor")
    assert "rule_packs" in aa["allowed_tabs"]


# ── CF-06 UserOut schema fields ───────────────────────────────────────────────


def test_user_out_has_persona_fields():
    from schemas import UserOut

    fields = set(UserOut.model_fields.keys())
    assert "persona_role" in fields
    assert "allowed_tabs" in fields
    assert "allowed_actions" in fields


def test_sample_in_has_domain_context():
    from schemas import SampleIn

    fields = set(SampleIn.model_fields.keys())
    assert "domain_context" in fields


def test_enhanced_trace_out_has_executive_steps():
    from schemas import EnhancedTraceOut

    fields = set(EnhancedTraceOut.model_fields.keys())
    assert "executive_steps" in fields
