"""FND-064 — the IR plan must not commit to response times SARO cannot deliver.

v1.0 promised "<5 min" automated detection, 15-minute acknowledgement, and
1-hour P1 response over an email-only channel operated by one person — and it is
customer-facing via GET /api/v1/governance/ir-plan.

This pins the reconciliation in three places at once, because the failure mode
is not "a wrong number" but "three sources that disagree": the document, the
support model, and the API payload a customer actually reads.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.regression

IRP = ROOT / "docs" / "incident-response-plan.md"
SUPPORT = ROOT / "docs" / "ops" / "support-model.md"
GOV = ROOT / "routers" / "governance.py"


def _irp() -> str:
    return IRP.read_text(encoding="utf-8")


# ── The undeliverable claims must be gone ───────────────────────────────────


def test_irp_no_longer_claims_sub_five_minute_automated_detection():
    doc = _irp()
    assert "Automated (<5 min)" not in doc
    assert "**Detect (0–5 min):**" not in doc


def test_irp_no_longer_promises_fifteen_minute_acknowledgement():
    doc = _irp()
    assert "Detection-to-acknowledgement: 15 minutes" not in doc


def test_irp_no_longer_describes_an_on_call_rotation_that_does_not_exist():
    doc = _irp()
    assert "@oncall" not in doc, "escalation names a Slack channel that does not exist"
    assert "On-Call Engineer" not in doc, "there is no on-call rotation"


def test_irp_no_longer_lists_superseded_railway_as_a_detection_trigger():
    assert "Railway health check failure" not in _irp()


# ── What replaced them must be truthful ─────────────────────────────────────


def test_irp_states_detection_matching_the_canary_reality():
    doc = _irp()
    assert "≤60 min" in doc or "<=60 min" in doc
    assert "two consecutive failures" in doc


def test_irp_is_versioned_with_a_changelog_explaining_the_correction():
    doc = _irp()
    assert "**Version:** 1.1" in doc
    assert "FND-064" in doc
    assert "v1.1 changelog" in doc


def test_severity_targets_live_in_exactly_one_place():
    """Two copies of a commitment table is how commitments drift."""
    doc = _irp()
    assert "support-model.md" in doc
    # The old inline target table must not have come back.
    assert "1-hour response, 2-hour restore" not in doc
    assert "4-hour response, 8-hour restore" not in doc


def test_notification_clock_is_separate_from_response_clock():
    """The insight that made reconciliation possible: 72h notification is
    achievable on email; a 15-minute response is not."""
    doc = _irp()
    assert "72 hours" in doc
    support = SUPPORT.read_text(encoding="utf-8")
    assert "72 hours" in support
    assert "Detection is separate from response" in support


# ── The customer-facing payload must agree with the documents ───────────────


def test_public_endpoint_reports_v11_and_the_committed_numbers():
    src = GOV.read_text(encoding="utf-8")
    assert '"version": "1.1"' in src
    assert '"sla_hours": 72' in src, "breach notification must be the 72h clock"
    assert "sla_basis" in src, "each number must say which clock it is"
    assert "FND-064" in src, "the constraint should be visible at the code site"


def test_public_endpoint_no_longer_implies_one_hour_breach_response():
    """v1.0 served sla_hours=1 for data-breach, reading as a 1-hour response."""
    src = GOV.read_text(encoding="utf-8")
    breach_block = src[src.index('"id": "data-breach"'):]
    breach_block = breach_block[: breach_block.index("}")]
    assert '"sla_hours": 1,' not in breach_block


def test_support_hours_are_stated_rather_than_implied_always_on():
    src = GOV.read_text(encoding="utf-8")
    assert "support_hours" in src
    assert "Mon-Fri" in src


def test_support_model_admits_the_out_of_hours_reality():
    """The sentence a buyer most needs and is least likely to be told."""
    support = SUPPORT.read_text(encoding="utf-8")
    assert "best-effort" in support.lower()
    assert "Saturday" in support or "next morning" in support.lower()
