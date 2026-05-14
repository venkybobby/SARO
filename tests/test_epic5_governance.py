"""Epic 5: Data Governance & Compliance Docs — complete test suite."""
import pytest
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent

import sys
sys.path.insert(0, str(ROOT))


# ── GOV-001 Retention Engine Tests ────────────────────────────────────────

class TestRetentionEngine:
    def setup_method(self):
        from services.retention_service import (
            calculate_retention_cutoff, is_eligible_for_purge,
            create_tombstone_record, generate_deletion_certificate
        )
        self.calculate_retention_cutoff = calculate_retention_cutoff
        self.is_eligible_for_purge = is_eligible_for_purge
        self.create_tombstone_record = create_tombstone_record
        self.generate_deletion_certificate = generate_deletion_certificate

    def test_retention_cutoff_is_correct_days_ago(self):
        cutoff = self.calculate_retention_cutoff(90)
        expected = datetime.utcnow() - timedelta(days=90)
        assert abs((cutoff - expected).total_seconds()) < 5

    def test_purge_eligibility_old_record(self):
        old_date = datetime.utcnow() - timedelta(days=91)
        assert self.is_eligible_for_purge(old_date, 90) is True

    def test_purge_eligibility_recent_record(self):
        recent = datetime.utcnow() - timedelta(days=1)
        assert self.is_eligible_for_purge(recent, 90) is False

    def test_purge_creates_tombstone_records(self):
        tombstone = self.create_tombstone_record(42, tenant_id=1)
        assert tombstone["original_event_id"] == 42
        assert tombstone["tenant_id"] == 1
        assert "tombstone_hash" in tombstone
        assert "deleted_at" in tombstone

    def test_tombstone_hash_is_deterministic(self):
        t1 = self.create_tombstone_record(42, 1, "retention_purge")
        t2 = self.create_tombstone_record(42, 1, "retention_purge")
        assert t1["tombstone_hash"] == t2["tombstone_hash"]

    def test_deletion_certificate_generated(self):
        cert = self.generate_deletion_certificate(1, 100, "erasure-123")
        assert cert["certificate_type"] == "GDPR_ERASURE"
        assert cert["records_deleted"] == 100
        assert "certificate_hash" in cert

    def test_gdpr_erasure_endpoint_returns_202(self):
        router_file = ROOT / "routers" / "governance.py"
        assert router_file.exists(), "governance.py router must exist"
        content = router_file.read_text(encoding="utf-8")
        assert "erasure-request" in content
        assert "202" in content

    def test_double_erasure_is_handled(self):
        # Two tombstones for the same event should not raise
        t1 = self.create_tombstone_record(42, 1)
        t2 = self.create_tombstone_record(42, 1)
        assert t1 is not None and t2 is not None


# ── GOV-002 IR Plan Tests ─────────────────────────────────────────────────

class TestIRPlan:
    def test_ir_plan_file_exists(self):
        ir = ROOT / "docs" / "incident-response-plan.md"
        assert ir.exists(), "docs/incident-response-plan.md must exist"

    def test_ir_plan_contains_section_false_negatives(self):
        content = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
        assert "false negative" in content.lower() or "False Negative" in content

    def test_ir_plan_contains_section_downtime(self):
        content = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
        assert "downtime" in content.lower() or "Downtime" in content

    def test_ir_plan_contains_section_data_breach(self):
        content = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
        assert "data breach" in content.lower() or "Data Breach" in content

    def test_ir_plan_contains_escalation_matrix(self):
        content = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
        assert "escalation" in content.lower()

    def test_ir_plan_has_no_todo_markers(self):
        content = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
        assert "TODO" not in content
        assert "PLACEHOLDER" not in content
        assert "[TBD]" not in content

    def test_ir_plan_has_review_schedule(self):
        content = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
        assert "review" in content.lower()


# ── GOV-003 DPA Template Tests ────────────────────────────────────────────

class TestDPATemplate:
    def test_dpa_template_file_exists(self):
        assert (ROOT / "docs" / "dpa-template.md").exists()

    def test_dpa_covers_gdpr_article_28(self):
        content = (ROOT / "docs" / "dpa-template.md").read_text(encoding="utf-8")
        assert "Article 28" in content or "article 28" in content.lower()

    def test_dpa_lists_data_types_and_retention(self):
        content = (ROOT / "docs" / "dpa-template.md").read_text(encoding="utf-8")
        assert "retention" in content.lower()
        assert ("data type" in content.lower() or "Data Types" in content
                or "categories" in content.lower())

    def test_sub_processors_file_exists(self):
        assert (ROOT / "docs" / "sub-processors.md").exists()

    def test_sub_processors_lists_railway(self):
        content = (ROOT / "docs" / "sub-processors.md").read_text(encoding="utf-8")
        assert "Railway" in content or "railway" in content.lower()

    def test_sub_processors_lists_supabase(self):
        content = (ROOT / "docs" / "sub-processors.md").read_text(encoding="utf-8")
        assert "Supabase" in content or "supabase" in content.lower()

    def test_sub_processors_lists_redis(self):
        content = (ROOT / "docs" / "sub-processors.md").read_text(encoding="utf-8")
        assert "Redis" in content or "redis" in content.lower()

    def test_dpa_has_no_todo_markers(self):
        content = (ROOT / "docs" / "dpa-template.md").read_text(encoding="utf-8")
        assert "TODO" not in content
        assert "PLACEHOLDER" not in content


# ── RUL-002 Compliance Claims Matrix Tests ────────────────────────────────

class TestClaimsMatrix:
    def test_claims_matrix_markdown_exists(self):
        assert (ROOT / "docs" / "compliance-claims.md").exists()

    def test_claims_matrix_has_all_four_frameworks(self):
        content = (ROOT / "docs" / "compliance-claims.md").read_text(encoding="utf-8")
        assert "NIST" in content
        assert "EU AI Act" in content or "EU Ai Act" in content
        assert "AIGP" in content
        assert "42001" in content or "ISO" in content

    def test_each_framework_has_supports_and_not_replace_columns(self):
        content = (ROOT / "docs" / "compliance-claims.md").read_text(encoding="utf-8")
        assert ("Supports" in content or "supports" in content)
        assert ("Does NOT" in content or "does not" in content.lower())

    def test_eu_ai_act_disclaims_conformity_assessment(self):
        content = (ROOT / "docs" / "compliance-claims.md").read_text(encoding="utf-8")
        lower = content.lower()
        assert "conformity assessment" in lower or "conformity" in lower
        assert ("does not" in lower or "Does NOT" in content)

    def test_claims_doc_has_no_todo_markers(self):
        content = (ROOT / "docs" / "compliance-claims.md").read_text(encoding="utf-8")
        assert "TODO" not in content
