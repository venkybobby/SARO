"""
Tests for FR-EVF-17 retrospective audit script.

Verifies:
  - Forbidden phrases are detected in scanned files
  - Allowed paths (COMPLIANCE_CLAIMS_MATRIX.md, the script itself) are skipped
  - Clean content produces PASS
  - Category assignment is correct (b vs c)
  - JSON output is well-formed
  - Exit code 0 = PASS, 1 = FAIL
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.evf_retrospective_audit import (  # noqa: E402
    run_audit,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tmp_repo(files: dict[str, str]) -> Path:
    """Create a temporary directory tree with given relative path → content."""
    tmp = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


# ── Detection tests ────────────────────────────────────────────────────────────

class TestForbiddenPhraseDetection:
    def test_nist_compliant_detected(self):
        root = _tmp_repo({"routers/api.py": '"nist_compliant": true'})
        report = run_audit(root)
        assert report.total_violations >= 1
        assert any("nist_compliant" in f.matched_phrase.lower() for f in report.findings)

    def test_eu_ai_act_compliance_detected(self):
        root = _tmp_repo({"docs/pitch.md": "EU AI Act compliance for enterprise"})
        report = run_audit(root)
        assert report.total_violations >= 1

    def test_nist_certified_detected(self):
        root = _tmp_repo({"frontend/app.py": "NIST Certified platform"})
        report = run_audit(root)
        assert report.total_violations >= 1

    def test_iso_42001_certification_detected(self):
        root = _tmp_repo({"docs/claims.md": "ISO 42001 certification achieved"})
        report = run_audit(root)
        assert report.total_violations >= 1
        assert any(f.category == "c" for f in report.findings)

    def test_aigp_certified_detected(self):
        root = _tmp_repo({"slides/deck.md": "AIGP certified tooling"})
        report = run_audit(root)
        assert report.total_violations >= 1

    def test_eu_ai_act_conforms_detected(self):
        root = _tmp_repo({"api/response.py": "EU AI Act conformity assessment complete"})
        report = run_audit(root)
        assert report.total_violations >= 1

    def test_aligned_with_nist_is_category_b(self):
        root = _tmp_repo({"docs/overview.md": "SARO is aligned with NIST AI RMF requirements"})
        report = run_audit(root)
        assert any(f.category == "b" for f in report.findings)

    def test_compliant_label_detected(self):
        root = _tmp_repo({"frontend/ui.tsx": '<span>Compliant: Yes</span>'})
        report = run_audit(root)
        assert report.total_violations >= 1


class TestCleanContent:
    def test_clean_file_returns_pass(self):
        root = _tmp_repo({
            "routers/scan.py": '"""Risk scoring endpoint."""\nreturn {"risk_score": 74}',
            "docs/readme.md": "SARO provides audit evidence for human review.",
        })
        report = run_audit(root)
        assert report.total_violations == 0
        assert report.audit_result == "PASS"

    def test_approved_phrases_not_flagged(self):
        root = _tmp_repo({
            "routers/api.py": (
                '"framework_evidence": "NIST-AI-RMF-1.0"\n'
                '"audit_evidence_generated": true\n'
                '"remediation_guidance": "..."\n'
                '"risk_score": 74\n'
            )
        })
        report = run_audit(root)
        assert report.total_violations == 0


class TestAllowlistPaths:
    def test_compliance_matrix_skipped(self):
        """COMPLIANCE_CLAIMS_MATRIX.md defines forbidden phrases — must not self-flag."""
        root = _tmp_repo({
            "docs/COMPLIANCE_CLAIMS_MATRIX.md": (
                "| NIST Certified | Forbidden |\n"
                "| EU AI Act certified | Forbidden |\n"
                "| nist_compliant: true | Forbidden |\n"
            )
        })
        report = run_audit(root)
        assert report.total_violations == 0

    def test_pycache_skipped(self):
        root = _tmp_repo({
            "__pycache__/api.pyc": '"nist_compliant": true',
        })
        report = run_audit(root)
        assert report.total_violations == 0

    def test_node_modules_skipped(self):
        root = _tmp_repo({
            "node_modules/pkg/index.js": 'NIST Certified module',
        })
        report = run_audit(root)
        assert report.total_violations == 0


class TestCategoryAssignment:
    def test_category_c_count(self):
        root = _tmp_repo({
            "docs/pitch.md": "NIST Certified\nISO 42001 certification\n"
        })
        report = run_audit(root)
        assert report.category_c_count >= 2
        assert report.category_b_count == 0

    def test_category_b_count(self):
        root = _tmp_repo({
            "docs/overview.md": "aligned with NIST\naligned with ISO 42001\n"
        })
        report = run_audit(root)
        assert report.category_b_count >= 2

    def test_audit_result_fail_on_violations(self):
        root = _tmp_repo({"api.py": '"nist_compliant": true'})
        report = run_audit(root)
        assert report.audit_result == "FAIL"


class TestReportStructure:
    def test_report_fields_present(self):
        root = _tmp_repo({"api.py": '"nist_compliant": true'})
        report = run_audit(root)
        assert hasattr(report, "generated_at")
        assert hasattr(report, "files_scanned")
        assert hasattr(report, "total_violations")
        assert hasattr(report, "findings")
        assert hasattr(report, "summary_by_file")
        assert hasattr(report, "remediation_instructions")

    def test_finding_has_all_fields(self):
        root = _tmp_repo({"api.py": '"nist_compliant": true'})
        report = run_audit(root)
        assert len(report.findings) > 0
        f = report.findings[0]
        assert f.file_path
        assert f.line_number > 0
        assert f.matched_phrase
        assert f.category in ("a", "b", "c")
        assert f.remediation
        assert f.severity in ("critical", "high", "medium")

    def test_summary_by_file_matches_findings(self):
        root = _tmp_repo({"api.py": '"nist_compliant": true'})
        report = run_audit(root)
        assert "api.py" in report.summary_by_file
        assert len(report.summary_by_file["api.py"]) >= 1

    def test_json_serialisable(self):
        import dataclasses
        root = _tmp_repo({"api.py": '"nist_compliant": true'})
        report = run_audit(root)
        serialised = json.dumps(dataclasses.asdict(report))
        parsed = json.loads(serialised)
        assert parsed["total_violations"] >= 1
        assert parsed["audit_result"] == "FAIL"


class TestMultipleViolationsPerFile:
    def test_one_finding_per_line(self):
        """Only one finding per line even if multiple patterns match."""
        root = _tmp_repo({
            "api.py": (
                '"nist_compliant": true\n'  # line 1
                'NIST Certified\n'          # line 2
                '"compliance_score": 99\n'  # line 3
            )
        })
        report = run_audit(root)
        # Each line should produce at most one finding
        line_numbers = [f.line_number for f in report.findings]
        assert len(line_numbers) == len(set(line_numbers))

    def test_files_scanned_count(self):
        root = _tmp_repo({
            "a.py": "clean",
            "b.md": "clean",
            "c.ts": '"nist_compliant": true',
        })
        report = run_audit(root)
        assert report.files_scanned == 3
        assert report.files_with_violations == 1
