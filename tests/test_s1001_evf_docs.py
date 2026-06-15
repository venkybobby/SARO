"""S-1001 / S-1205: EVF artifact pack + pilot collateral existence and section checks.

Asserts the six EVF artefacts exist (FR-EVF-01/03/04/16/18/20) and that the three
markdown docs authored here carry their mandatory sections and a legal-approval
placeholder. Also checks the pilot one-pager defines the 1-BU / 25-model scope.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.unit]

ROOT = Path(__file__).resolve().parent.parent
EVF = ROOT / "docs" / "evf"


def _read(p: Path) -> str:
    assert p.exists(), f"missing required artefact: {p.relative_to(ROOT)}"
    return p.read_text(encoding="utf-8")


def test_six_evf_artifacts_exist():
    # FR-EVF-03 COI, FR-EVF-04 SOW, FR-EVF-16 language tier — shipped as .docx/.txt.
    docx_or_txt = [
        "evf_coi_declaration_form",
        "evf_sow_template",
        "evf_language_tier_policy",
    ]
    for stem in docx_or_txt:
        assert (EVF / f"{stem}.docx").exists() or (EVF / f"{stem}.txt").exists(), (
            f"missing EVF artefact: {stem}"
        )
    # FR-EVF-01/18/20 — authored as markdown.
    for name in (
        "sme-qualification-criteria.md",
        "claims-challenge-protocol.md",
        "evf-retention-addendum.md",
    ):
        _read(EVF / name)


@pytest.mark.parametrize(
    "name, must_contain",
    [
        ("sme-qualification-criteria.md", ["Independence", "Credential", "Disqualif", "FR-EVF-01"]),
        ("claims-challenge-protocol.md", ["Triage", "Adjudication", "Escalation", "FR-EVF-18"]),
        ("evf-retention-addendum.md", ["Retention Schedule", "7 years", "Immutab", "FR-EVF-20"]),
    ],
)
def test_evf_md_mandatory_sections(name, must_contain):
    text = _read(EVF / name)
    for token in must_contain:
        assert token in text, f"{name} missing mandatory content: {token!r}"


def test_evf_md_have_legal_approval_placeholder():
    for name in ("sme-qualification-criteria.md", "claims-challenge-protocol.md", "evf-retention-addendum.md"):
        text = _read(EVF / name)
        assert "Legal approval" in text and "Approved by" in text


def test_pilot_one_pager_defines_bounded_scope():
    text = _read(ROOT / "docs" / "pilot-one-pager.md")
    assert "One" in text and "25" in text          # one BU / max 25 models
    assert "Compliance Lead" in text
    assert "vendor ai output" in text.lower()
