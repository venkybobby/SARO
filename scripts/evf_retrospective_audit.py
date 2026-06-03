#!/usr/bin/env python3
"""
FR-EVF-17 — Retrospective Compliance Claims Audit Script
=========================================================
Scans the entire SARO repository for forbidden compliance phrases and
classifies every finding under the 3-tier remediation system:

  Category (a) QCO available  — update artefact with QCO reference
  Category (b) QCO not yet available — remove or replace with Tier 2 language
  Category (c) QCO not planned / Tier 3 — remove claim entirely

Exit codes:
  0  — no violations found (audit passes)
  1  — violations found (audit fails — remediation required)

Usage:
  python scripts/evf_retrospective_audit.py [--output report.json] [--root /path/to/repo]

Refs: FR-EVF-17, AC-17a, AC-17b | SARO-RISK-001
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ── Forbidden phrase registry ─────────────────────────────────────────────────
# Each entry: (pattern, category, approved_replacement)
# Category: "b" = replace with Tier 2 | "c" = remove entirely

FORBIDDEN_PHRASES: list[tuple[re.Pattern, str, str]] = [
    # EU AI Act violations
    (re.compile(r"EU\s+AI\s+Act\s+complian(t|ce)", re.I),
     "c", "Remove — no QCO issued. Omit EU AI Act alignment reference."),
    (re.compile(r"complian(t|ce)\s+with\s+EU\s+AI\s+Act", re.I),
     "c", "Remove — no QCO issued. Omit EU AI Act alignment reference."),
    (re.compile(r"EU\s+AI\s+Act\s+certif(ied|ication)", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    (re.compile(r"EU\s+AI\s+Act\s+conform(s|ance|ity)", re.I),
     "c", "Remove — SARO never asserts conformity. Omit entirely."),
    # NIST violations
    (re.compile(r"nist[_\s-]?(ai[_\s-]?rmf)?[_\s-]?complian(t|ce)", re.I),
     "c", "Remove — no QCO issued. Omit NIST AI RMF alignment reference."),
    (re.compile(r"nist[_\s-]?certif(ied|ication)", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    (re.compile(r'"nist_compliant"\s*:\s*true', re.I),
     "c", 'Replace with "framework_evidence": "NIST-AI-RMF-1.0" (allowed key).'),
    (re.compile(r"NIST\s+Certified", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    # AIGP violations
    (re.compile(r"AIGP\s+certif(ied|ication)", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    (re.compile(r"certif(ied|ication)\s+under\s+AIGP", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    # ISO 42001 violations
    (re.compile(r"ISO\s+42001\s+certif(ied|ication)", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    (re.compile(r"ISO\s+42001\s+complian(t|ce)", re.I),
     "c", "Remove — no QCO issued. Omit ISO 42001 alignment reference."),
    (re.compile(r"ISO\s+42001\s+conform(s|ance|ity)", re.I),
     "c", "Remove — SARO never asserts conformity. Omit entirely."),
    # Generic compliance overclaims
    (re.compile(r'"compliance_score"\s*:', re.I),
     "c", 'Replace with "risk_score" (approved key).'),
    (re.compile(r'"audit_passed"\s*:\s*true', re.I),
     "c", 'Replace with "audit_evidence_generated": true (approved key).'),
    (re.compile(r'"nist_compliant"\s*:', re.I),
     "c", 'Replace with "framework_evidence": "NIST-AI-RMF-1.0" (approved key).'),
    (re.compile(r'"compliance_fix"\s*:', re.I),
     "c", 'Replace with "remediation_guidance" (approved key).'),
    (re.compile(r"Compliant:\s*(Yes|No)", re.I),
     "c", 'Replace with "Risk score: {score}/100 — human review recommended".'),
    (re.compile(r"Audit:\s*Passed", re.I),
     "c", 'Replace with "TRACE evidence generated for auditor review".'),
    (re.compile(r"NIST\s+Certified|NIST\s+Approved", re.I),
     "c", "Remove — SARO never certifies. Omit entirely."),
    (re.compile(r"ensures?\s+EU\s+AI\s+Act\s+compliance", re.I),
     "c", 'Replace with "Supports EU AI Act documentation workflows".'),
    (re.compile(r"regulatory\s+approval\s+tool", re.I),
     "c", 'Replace with "evidence-based risk scoring".'),
    (re.compile(r"SARO\s+certifies?\s+compliance", re.I),
     "c", 'Replace with "SARO provides audit evidence".'),
    # Tier 2 candidates — has some EVF process but no QCO yet
    (re.compile(r"aligned?\s+with\s+(?:EU\s+AI\s+Act|NIST|AIGP|ISO\s+42001)", re.I),
     "b", 'Replace with Tier 2: "SARO is undergoing independent review for [Framework] coverage."'),
    (re.compile(r"meets?\s+(?:EU\s+AI\s+Act|NIST|AIGP|ISO\s+42001)\s+requirements?", re.I),
     "b", 'Replace with Tier 2: "SARO is undergoing independent review for [Framework] coverage."'),
    (re.compile(r"framework\s+complian(t|ce)", re.I),
     "b", 'Replace with Tier 2 language or remove if no QCO is in progress.'),
]

# ── Paths to scan ─────────────────────────────────────────────────────────────
SCAN_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt",
    ".html", ".yml", ".yaml", ".json", ".toml", ".rst",
    ".env.example", ".sh",
}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "saro-data-framework", ".mypy_cache", ".ruff_cache",
    "dist", "build", ".next",
}

# Binary / generated files to skip regardless of extension
SKIP_FILES = {
    "package-lock.json",
}

# Files explicitly known to contain forbidden phrases as examples/documentation
# (e.g., the compliance matrix itself defines what's forbidden)
ALLOWLIST_PATHS_CONTAINING = {
    "docs/COMPLIANCE_CLAIMS_MATRIX.md",  # defines the forbidden phrases — not a violation
    "scripts/evf_retrospective_audit.py",  # this script itself
    "docs/evf/evf_language_tier_policy.docx",  # Word doc — not scanned
    "docs/evf/evf_qco_template.docx",         # Word doc
    "docs/evf/evf_sow_template.docx",          # Word doc
    "docs/evf/evf_coi_declaration_form.docx",  # Word doc
}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Finding:
    file_path: str
    line_number: int
    line_text: str
    matched_phrase: str
    category: str          # "a" | "b" | "c"
    remediation: str
    severity: str          # "critical" | "high" | "medium"


@dataclass
class AuditReport:
    generated_at: str
    repo_root: str
    files_scanned: int
    files_with_violations: int
    total_violations: int
    category_a_count: int  # QCO available — update with ref
    category_b_count: int  # QCO not yet available — replace with Tier 2
    category_c_count: int  # remove entirely
    audit_result: str      # "PASS" | "FAIL"
    findings: list[Finding] = field(default_factory=list)
    summary_by_file: dict = field(default_factory=dict)
    remediation_instructions: str = ""


# ── Scanner ───────────────────────────────────────────────────────────────────

def _should_skip(path: Path, root: Path) -> bool:
    """Return True if this path should be excluded from scanning."""
    rel = path.relative_to(root)
    parts = rel.parts

    # Skip hidden dirs and known noise dirs
    for part in parts:
        if part in SKIP_DIRS or part.startswith("."):
            return True

    # Skip specific files
    if path.name in SKIP_FILES:
        return True

    # Skip files on the allowlist
    rel_str = str(rel).replace("\\", "/")
    for allowed in ALLOWLIST_PATHS_CONTAINING:
        if rel_str.endswith(allowed) or allowed in rel_str:
            return True

    return False


def _scan_file(path: Path, root: Path) -> list[Finding]:
    """Scan one file for forbidden phrases. Returns list of findings."""
    findings: list[Finding] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return findings

    for line_num, line in enumerate(text.splitlines(), start=1):
        for pattern, category, remediation in FORBIDDEN_PHRASES:
            match = pattern.search(line)
            if match:
                severity = "critical" if category == "c" else "high"
                findings.append(Finding(
                    file_path=str(path.relative_to(root)).replace("\\", "/"),
                    line_number=line_num,
                    line_text=line.strip()[:200],
                    matched_phrase=match.group(0),
                    category=category,
                    remediation=remediation,
                    severity=severity,
                ))
                break  # one finding per line (avoid double-reporting)

    return findings


def run_audit(root: Path) -> AuditReport:
    """Walk the repo from root and return a completed AuditReport."""
    all_findings: list[Finding] = []
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped dirs in-place (prevents os.walk descending into them)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if filepath.suffix.lower() not in SCAN_EXTENSIONS:
                continue
            if _should_skip(filepath, root):
                continue

            files_scanned += 1
            findings = _scan_file(filepath, root)
            all_findings.extend(findings)

    # Group by file
    summary: dict[str, list[dict]] = {}
    for f in all_findings:
        summary.setdefault(f.file_path, []).append({
            "line": f.line_number,
            "matched": f.matched_phrase,
            "category": f.category,
            "action": f.remediation,
        })

    cat_a = sum(1 for f in all_findings if f.category == "a")
    cat_b = sum(1 for f in all_findings if f.category == "b")
    cat_c = sum(1 for f in all_findings if f.category == "c")

    report = AuditReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        repo_root=str(root),
        files_scanned=files_scanned,
        files_with_violations=len(summary),
        total_violations=len(all_findings),
        category_a_count=cat_a,
        category_b_count=cat_b,
        category_c_count=cat_c,
        audit_result="PASS" if not all_findings else "FAIL",
        findings=all_findings,
        summary_by_file=summary,
        remediation_instructions=_build_instructions(cat_a, cat_b, cat_c),
    )
    return report


def _build_instructions(cat_a: int, cat_b: int, cat_c: int) -> str:
    lines = [
        "FR-EVF-17 Remediation Instructions",
        "=" * 40,
        "",
        f"Category (a) — QCO Available [{cat_a} findings]:",
        "  Update the artefact to include the QCO reference number.",
        '  Use Tier 1 language: "Externally Reviewed — QCO [ref] | [SME Firm] | [Date]"',
        "",
        f"Category (b) — QCO Not Yet Available [{cat_b} findings]:",
        "  Replace the compliance claim with Tier 2 approved language:",
        '  "SARO is undergoing independent review for [Framework] coverage.',
        '   Claims will be published upon QCO completion."',
        "  OR remove the claim entirely if review has not started.",
        "",
        f"Category (c) — Remove Entirely [{cat_c} findings]:",
        "  Remove the claim. No compliance alignment reference permitted",
        "  until a QCO reference number is assigned (FR-EVF-16 Tier 3).",
        "",
        "AC-17b deadline: all Category (b) and (c) artefacts must be",
        "remediated within 30 days of the audit report sign-off.",
        "",
        "See docs/COMPLIANCE_CLAIMS_MATRIX.md for approved language.",
    ]
    return "\n".join(lines)


# ── Output formatters ─────────────────────────────────────────────────────────

def _print_console(report: AuditReport) -> None:
    """Print a human-readable summary to stdout."""
    sep = "-" * 72

    print(f"\n{'='*72}")
    print("  SARO FR-EVF-17 — Retrospective Compliance Claims Audit")
    print(f"  Generated: {report.generated_at}")
    result_label = "PASS" if report.audit_result == "PASS" else "FAIL"
    print(f"  Result: {result_label}")
    print(f"{'='*72}\n")

    print(f"Files scanned       : {report.files_scanned}")
    print(f"Files with violations: {report.files_with_violations}")
    print(f"Total violations    : {report.total_violations}")
    print(f"  Category (b) — replace with Tier 2 : {report.category_b_count}")
    print(f"  Category (c) — remove entirely      : {report.category_c_count}")

    if not report.findings:
        print("\nPASS: No forbidden compliance phrases found.\n")
        return

    print(f"\n{sep}")
    print("VIOLATIONS BY FILE")
    print(sep)

    for file_path, items in sorted(report.summary_by_file.items()):
        print(f"\n  {file_path}  [{len(items)} violation(s)]")
        for item in items:
            cat_label = f"[Cat-{item['category'].upper()}]"
            print(f"   Line {item['line']:>4}  {cat_label}  matched: \"{item['matched']}\"")
            print(f"            Action: {item['action']}")

    print(f"\n{sep}")
    print(report.remediation_instructions)
    print(sep)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="FR-EVF-17 Retrospective Compliance Claims Audit"
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).parent.parent),
        help="Repository root to scan (default: parent of this script)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON report to this file path (optional)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Suppress console output; write JSON only (requires --output)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: repo root '{root}' is not a directory", file=sys.stderr)
        return 2

    report = run_audit(root)

    if not args.json_only:
        _print_console(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Convert dataclasses to plain dicts for JSON serialisation
        report_dict = asdict(report)
        out_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        if not args.json_only:
            print(f"\nJSON report written to: {out_path}")

    return 0 if report.audit_result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
