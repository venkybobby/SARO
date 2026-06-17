"""STORY-337 — Claims-consistency guard (locked Compliance Claims Matrix).

The locked claims are a versioned, machine-checkable registry. Mechanical
violations are blocked: an external-model runtime call (delegated to STORY-336)
and AIGP-as-"certification"/"framework" framing. A locked claim cannot change
silently — the integrity lock fails CI until the change is made explicit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grc.guards.claims_registry import (
    LOCKED_CLAIMS,
    REGISTRY_VERSION,
    ClaimsRegistryError,
    assert_registry_integrity,
    check_framing,
    registry_digest,
    scan_files,
    verify_external_model_claim,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- AC: the claims registry exists and is versioned ------------------------


def test_registry_exists_and_is_versioned() -> None:
    assert REGISTRY_VERSION
    ids = {c.id for c in LOCKED_CLAIMS}
    # The seven seeded locked claims from the Compliance Claims Matrix.
    for required in {
        "no-external-model-runtime",
        "no-compliance-certification",
        "human-in-the-loop",
        "no-write-to-client",
        "aigp-principles-only",
        "eu-ai-act-evidence-only",
        "iso-42001-lifecycle-only",
    }:
        assert required in ids, f"missing locked claim {required}"


def test_registry_integrity_holds() -> None:
    # The committed digest matches the current claims — no drift.
    assert_registry_integrity()


# --- AC: changing a locked claim cannot happen silently ---------------------


def test_silent_claim_change_breaks_integrity(monkeypatch: pytest.MonkeyPatch) -> None:
    import grc.guards.claims_registry as reg

    tampered = LOCKED_CLAIMS[:-1] + (
        reg.LockedClaim(
            id="no-write-to-client",
            statement="SARO now writes remediation directly to client systems.",
            source="(tampered)",
            mechanical="manual",
        ),
    )
    monkeypatch.setattr(reg, "LOCKED_CLAIMS", tampered)
    # The digest now differs from the committed lock → integrity fails loudly.
    assert registry_digest() != reg._locked_digest()
    with pytest.raises(ClaimsRegistryError):
        assert_registry_integrity()


# --- AC: an external-model runtime call is blocked (via STORY-336) ----------


def test_external_model_call_is_blocked(tmp_path: Path) -> None:
    (tmp_path / "rogue.py").write_text("import anthropic\n", encoding="utf-8")
    violation = verify_external_model_claim(repo_root=tmp_path, roots=[tmp_path])
    assert violation is not None
    assert "anthropic" in violation


def test_clean_product_path_satisfies_external_model_claim() -> None:
    # The real product path honours the claim (engine.py allowlisted by 336).
    assert verify_external_model_claim() is None


# --- AC: AIGP-as-certification / AIGP-as-framework is flagged ---------------


@pytest.mark.parametrize(
    "text",
    [
        "SARO provides AIGP certification for your system.",
        "We offer AIGP-certification out of the box.",
        "SARO is an AIGP framework for compliance.",
        "Our AIGP-framework maps every control.",
    ],
)
def test_framing_flags_aigp_certification_and_framework(text: str) -> None:
    assert check_framing(text), f"should flag: {text}"


@pytest.mark.parametrize(
    "text",
    [
        "Evidence package for an AIGP-certified human reviewer.",
        "Supports AIGP principles evaluation for human reviewers.",
        "SARO maps findings to AIGP principles for human sign-off.",
    ],
)
def test_framing_allows_matrix_approved_aigp_language(text: str) -> None:
    assert check_framing(text) == [], f"should NOT flag approved language: {text}"


def test_framing_suppression_marker_allows_quoted_forbidden_text() -> None:
    # A line that deliberately quotes the forbidden phrasing (e.g. a "do not say"
    # example) can opt out with an inline marker.
    line = 'Never say "AIGP certification".  # claims-allow'
    assert check_framing(line) == []


# --- AC: positive — a compliant story passes the guard ----------------------


def test_compliant_text_passes() -> None:
    text = (
        "SARO generates audit evidence supporting AIGP principles evaluation. "
        "Human review and sign-off by qualified personnel is required."
    )
    assert check_framing(text) == []


def test_scan_files_flags_a_noncompliant_doc(tmp_path: Path) -> None:
    bad = tmp_path / "pitch.md"
    bad.write_text("SARO delivers AIGP certification today.\n", encoding="utf-8")
    violations = scan_files([bad], repo_root=tmp_path)
    assert violations and violations[0].path == "pitch.md"


def test_certification_with_trailing_reviewer_noun_still_flagged() -> None:
    # F1: a trailing reviewer-noun must not silence a genuine SARO certification
    # claim. "AIGP certification reviewer badges" is NOT the approved phrasing.
    assert check_framing("SARO issues AIGP certification reviewer badges.")


@pytest.mark.parametrize(
    "text",
    [
        "We offer AIGP‑certification.",  # U+2011 non-breaking hyphen
        "Get AIGP‐certification today.",  # U+2010 hyphen
        "**AIGP** certification included.",  # markdown emphasis between tokens
    ],
)
def test_framing_resists_unicode_and_markdown_evasion(text: str) -> None:
    assert check_framing(text), f"normalised form should flag: {text!r}"


def test_exclude_is_path_anchored_not_basename(tmp_path: Path) -> None:
    # F4: a NEW file merely reusing an excluded basename is still scanned.
    sneaky = tmp_path / "specs" / "stories"
    sneaky.mkdir(parents=True)
    f = sneaky / "compliance-claims.md"  # excluded only at docs/compliance-claims.md
    f.write_text("SARO provides AIGP certification.\n", encoding="utf-8")
    violations = scan_files([f], repo_root=tmp_path)
    assert violations, "a basename-collision file must not inherit the exemption"


def test_scan_files_excludes_the_matrix_itself() -> None:
    # The matrix and audit log legitimately enumerate forbidden phrasing; scanning
    # them must not self-trip.
    violations = scan_files(
        [REPO_ROOT / "docs" / "COMPLIANCE_CLAIMS_MATRIX.md"], repo_root=REPO_ROOT
    )
    assert violations == []
