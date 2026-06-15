"""S-1003 (AC-09b): active prohibited-language lint over live claim surfaces.

The FR-EVF-17 retrospective audit (scripts/evf_retrospective_audit.py) runs repo-wide
and tolerates legacy/superseded docs. This test is the *gating* complement: it asserts
the surfaces a customer actually sees — frontend UI strings, API routers/schemas, and the
EVF/compliance services that render framework labels — carry ZERO Category-(c) overclaims
("certified", "compliant", "conformity", etc.). Unlike the one-off JSON report, this fails CI.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evf_retrospective_audit import FORBIDDEN_PHRASES, _scan_file

pytestmark = [pytest.mark.regression, pytest.mark.unit]

ROOT = Path(__file__).resolve().parent.parent

# Live claim surfaces — what a prospect/customer reads. Legacy docs are governed
# separately by the repo-wide retrospective audit and are intentionally excluded.
_SURFACE_GLOBS = [
    ("frontend/src", ("*.jsx", "*.js", "*.tsx", "*.ts")),
    ("routers", ("*.py",)),
    ("services", ("*.py",)),
]
_SURFACE_FILES = [ROOT / "schemas.py"]


def _surface_files() -> list[Path]:
    files = [p for p in _SURFACE_FILES if p.exists()]
    for subdir, patterns in _SURFACE_GLOBS:
        base = ROOT / subdir
        if not base.exists():
            continue
        for pat in patterns:
            files.extend(base.rglob(pat))
    return [f for f in files if "node_modules" not in f.parts and "dist" not in f.parts]


def test_phrase_registry_is_nonempty():
    # Guard against a silently-empty registry making the lint vacuous.
    assert len(FORBIDDEN_PHRASES) >= 10


def test_no_prohibited_overclaims_on_live_surfaces():
    violations = []
    for path in _surface_files():
        for f in _scan_file(path, ROOT):
            if f.category == "c":  # critical: remove-entirely overclaims
                violations.append(f"{f.file_path}:{f.line_number}  \"{f.matched_phrase}\"  ({f.line_text})")

    assert not violations, (
        "Prohibited compliance overclaims on live claim surfaces (S-1003 AC-09b):\n  "
        + "\n  ".join(violations)
    )
