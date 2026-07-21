"""STORY-371 — support model, IRP v1.1, and the tabletop exercise.

The reconciliation itself is pinned by
`tests/regression/test_fnd_064_ir_plan_response_commitments.py`. This file
covers the story's own acceptance criteria and, in particular, that the tabletop
was a real exercise — one that found gaps and filed them — rather than a
document asserting that an exercise happened.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.unit

SUPPORT = ROOT / "docs" / "ops" / "support-model.md"
IRP = ROOT / "docs" / "incident-response-plan.md"
TABLETOP_DIR = ROOT / "docs" / "ops" / "tabletop"
TABLETOP = TABLETOP_DIR / "2026-07-21-leaked-credential.md"
SLA = ROOT / "docs" / "legal" / "sla-draft-v0.1.md"
FINDINGS = ROOT / "quality" / "findings.md"


def _flat(path: Path) -> str:
    """Read with whitespace collapsed.

    Prose in these docs is hard-wrapped, so a phrase can straddle a newline.
    Asserting on the raw text would make the tests hostage to line breaks and
    tempt someone to reflow a document to satisfy a matcher.
    """
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


# ── AC-1: the support model ─────────────────────────────────────────────────


def test_support_model_defines_s1_to_s4_with_targets():
    doc = SUPPORT.read_text(encoding="utf-8")
    for sev in ("S1", "S2", "S3", "S4"):
        assert f"**{sev}" in doc, f"{sev} not defined"
    assert "1 business hour" in doc
    assert "Response (outside hours)" in doc


def test_support_model_states_hours_and_solo_operator_model():
    doc = SUPPORT.read_text(encoding="utf-8")
    assert "Monday–Friday" in doc
    assert "America/Chicago" in doc
    assert "operated by **one person**" in doc
    assert "no on-call rotation" in doc.lower()


def test_support_model_separates_notification_from_response():
    """The distinction that made honest targets possible."""
    doc = _flat(SUPPORT)
    assert "Detection is separate from response" in doc
    assert "72 hours" in doc
    assert "the agreement governs" in doc, "BAA/DPA must be able to override the floor"


def test_support_model_flags_the_missing_backup_responder():
    """The largest gap in a solo model must not be silently omitted."""
    doc = SUPPORT.read_text(encoding="utf-8")
    assert "[HUMAN — OPEN]" in doc
    assert "no backup responder" in doc.lower()


def test_support_model_costs_out_the_paging_upgrade():
    """An owner deciding whether to fund paging needs the comparison."""
    doc = SUPPORT.read_text(encoding="utf-8")
    assert "What changes with a paging tier" in doc
    assert "24×7" in doc or "24x7" in doc
    assert "willing to be woken" in doc


def test_support_model_targets_do_not_exceed_what_the_channel_supports():
    """No sub-hour response commitment may appear while alerting is email-only."""
    doc = SUPPORT.read_text(encoding="utf-8")
    committed = doc[doc.index("## 3. Response and resolution targets"): doc.index("## 4.")]
    assert not re.search(r"\b(5|10|15|30)[- ]minute response\b", committed), (
        "a sub-hour response target reappeared in the committed table"
    )


# ── AC-2: IRP v1.1 ──────────────────────────────────────────────────────────


def test_irp_is_v11_and_links_the_support_model():
    doc = IRP.read_text(encoding="utf-8")
    assert "**Version:** 1.1" in doc
    assert "support-model.md" in doc
    assert "End of Incident Response Plan v1.1" in doc


def test_irp_contains_a_postmortem_template():
    doc = IRP.read_text(encoding="utf-8")
    assert "Post-mortem template" in doc
    for section in ("Customer impact", "Timeline", "Root cause", "Actions"):
        assert section in doc, f"post-mortem template missing {section}"


def test_postmortem_template_requires_a_systemic_action():
    """'Be more careful' is not a corrective action."""
    doc = _flat(IRP)
    assert "not an action" in doc
    assert "Evidence integrity affected?" in doc


def test_irp_maps_old_p_severities_to_new_s_severities():
    """Someone holding v1.0 must be able to translate."""
    assert "P1≡S1" in IRP.read_text(encoding="utf-8")


# ── AC-3: the tabletop actually happened ────────────────────────────────────


def test_tabletop_notes_are_committed():
    assert TABLETOP.exists(), "tabletop notes missing"
    assert TABLETOP_DIR.is_dir()


def test_tabletop_used_the_real_fnd_003_scenario():
    doc = TABLETOP.read_text(encoding="utf-8")
    assert "FND-003" in doc
    assert "leaked" in doc.lower() or "credential" in doc.lower()


def test_tabletop_states_nothing_was_executed():
    """A desk exercise must not be mistaken for a rehearsed rotation."""
    doc = TABLETOP.read_text(encoding="utf-8")
    assert "Nothing in this exercise was executed" in doc


def test_tabletop_found_gaps_and_filed_them():
    """An exercise that finds nothing was not an exercise."""
    doc = TABLETOP.read_text(encoding="utf-8")
    assert "## Gaps found" in doc
    for fnd in ("FND-065", "FND-066", "FND-067"):
        assert fnd in doc, f"{fnd} not linked from the tabletop notes"
    assert "## What did not" in doc, "an all-positive retrospective is not credible"


def test_tabletop_gaps_are_in_the_findings_ledger():
    ledger = FINDINGS.read_text(encoding="utf-8")
    for fnd in ("FND-065", "FND-066", "FND-067"):
        assert f"| {fnd} |" in ledger, f"{fnd} filed in notes but not in the ledger"


def test_tabletop_schedules_the_next_exercise():
    doc = TABLETOP.read_text(encoding="utf-8")
    assert "Next exercise" in doc
    assert "IRP" in doc or "incident-response-plan" in doc


# ── AC-4: gap-tracker linkage stays accurate ────────────────────────────────


def test_sla_gate_reflects_the_reconciliation_without_overclaiming():
    """FND-064 is closed; counsel review and the backup responder are not."""
    doc = SLA.read_text(encoding="utf-8")
    assert "FND-064 reconciled" in doc
    assert "Still required before external use" in doc
    assert "counsel review" in doc.lower()
    assert "named backup responder" in doc.lower()


def test_fnd_064_is_marked_pinned_in_the_ledger():
    ledger = FINDINGS.read_text(encoding="utf-8")
    row = [ln for ln in ledger.splitlines() if ln.startswith("| FND-064 ")][0]
    assert row.rstrip().endswith("| pinned |")
    assert "test_fnd_064_ir_plan_response_commitments" in row


def test_auth_registry_justification_was_corrected():
    """I asserted a mechanism that did not exist (FM-2); the fix must stick.

    The tabletop found the claim was false, this test pinned the correction, and
    FND-065 then made it true — login is now genuinely audited. What must never
    return is the original unverified justification.
    """
    from services.admin_audit_registry import classification

    src = (ROOT / "services" / "admin_audit_registry.py").read_text(encoding="utf-8")
    assert "auth events handled by the auth path" not in src, (
        "the inaccurate justification returned"
    )
    assert classification("POST", "/api/v1/auth/token") == "AUDITED"
    # Register/bootstrap coverage is still outstanding and must stay stated.
    assert "still outstanding (FND-065)" in src
