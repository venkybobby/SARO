"""STORY-369 — SLO definitions and the external SLA draft.

These are commitment documents. The tests therefore check that they *under*
promise relative to the architecture, that every target names the signal it is
computed from, and that the SLA cannot quietly become issuable while its
dependency (FND-064) is unreconciled.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.unit

SLO = ROOT / "docs" / "ops" / "slo.md"
SLA = ROOT / "docs" / "legal" / "sla-draft-v0.1.md"
ALERTS = ROOT / "docs" / "ops" / "alerts.md"
FINDINGS = ROOT / "quality" / "findings.md"
FLY = ROOT / "fly.toml"


def _slo() -> str:
    return SLO.read_text(encoding="utf-8")


def _sla() -> str:
    return SLA.read_text(encoding="utf-8")


# ── AC-1: SLOs defined and tied to real signals ─────────────────────────────


def test_slo_document_exists_with_the_required_indicators():
    doc = _slo()
    for sli in ("Availability", "latency", "Ingestion freshness"):
        assert sli.lower() in doc.lower(), f"SLO doc missing {sli}"


def test_every_sli_names_the_metric_it_is_computed_from():
    """An SLI without a wired-up signal is an aspiration."""
    doc = _slo()
    for signal in (
        "saro_db_reachable",
        "saro_http_request_duration_seconds",
        "saro_ingestion_lag_seconds",
        "canary_evaluation.py",
    ):
        assert signal in doc, f"SLI table does not reference {signal}"


def test_ingestion_slo_matches_the_alert_threshold_exactly():
    """An SLO that disagrees with its alert trains the operator to ignore one."""
    assert "90 min" in _slo()
    assert "5400" in ALERTS.read_text(encoding="utf-8")  # 90 min in seconds


def test_slo_states_the_single_machine_single_region_constraint():
    doc = _slo()
    assert "min_machines_running" in doc
    assert "dfw" in doc
    assert "Supabase" in doc, "compound dependency availability must be stated"


def test_slo_explicitly_rejects_a_999_target():
    """The number the architecture cannot support must be refused in writing."""
    doc = _slo()
    assert "99.9%" in doc
    assert "not achievable" in doc.lower() or "not achievable or measurable" in doc.lower()


# ── The honesty that matters most: measurement is not yet in place ──────────


def test_slo_discloses_that_continuous_measurement_is_missing():
    """Targets exist; a TSDB does not. Claiming measured SLOs would be false."""
    doc = _slo()
    assert "not yet in place" in doc.lower() or "not in place" in doc.lower()
    assert "Prometheus" in doc or "TSDB" in doc
    assert "counters reset" in doc.lower()


def test_slo_states_the_30_minute_measurement_floor():
    """A 30-min probe cannot substantiate a finer availability claim."""
    doc = _slo()
    assert "30-minute" in doc or "30 min" in doc
    assert "measurement floor" in doc.lower()


# ── AC-2: the external SLA draft ────────────────────────────────────────────


def test_sla_is_marked_draft_and_not_for_external_use():
    doc = _sla()
    assert "DRAFT" in doc
    assert "NOT FOR EXTERNAL USE" in doc
    assert "counsel" in doc.lower()


def test_sla_commits_to_995_not_999():
    doc = _sla()
    assert "99.5%" in doc
    # 99.9 may only appear as the number being refused, with its reason.
    if "99.9%" in doc:
        assert "could not honour" in doc or "not honour" in doc or "43 minutes" in doc


def test_sla_justifies_the_tier_and_gives_an_upgrade_path():
    doc = _sla()
    assert "Upgrade path" in doc
    assert "single machine" in doc.lower()
    assert "failover" in doc.lower()


def test_sla_defines_measurement_method_and_its_granularity():
    doc = _sla()
    assert "every 30 minutes" in doc.lower() or "30 minutes" in doc
    assert "granularity" in doc.lower()
    assert "Availability %" in doc, "the formula must be stated, not implied"


def test_sla_lists_exclusions_including_upstream_providers():
    doc = _sla()
    assert "Exclusions" in doc
    for exclusion in ("maintenance", "Customer-side", "Fly.io or Supabase", "Force majeure"):
        assert exclusion.lower() in doc.lower(), f"missing exclusion: {exclusion}"


def test_sla_states_maintenance_window_and_notice_period():
    doc = _sla()
    assert re.search(r"\d{2}:\d{2}[–-]\d{2}:\d{2} UTC", doc), "no concrete window"
    assert "72 hours" in doc


def test_sla_is_explicit_about_no_service_credits():
    """Omitting remedies lets a buyer assume a financially-backed guarantee."""
    doc = _sla()
    assert "No service credits" in doc


# ── AC-3: support model referenced, never duplicated ────────────────────────


def test_sla_points_at_the_support_model_rather_than_restating_it():
    doc = _sla()
    assert "STORY-371" in doc
    assert "not in this document" in doc.lower() or "deliberate pointer" in doc.lower()


def test_sla_does_not_restate_response_time_commitments():
    """Two sources of severity targets is exactly how commitments drift."""
    doc = _sla()
    # The SLA may name the source doc, but must not carry its own hour targets.
    assert not re.search(r"\bS1\b.*\b\d+\s*hour", doc), "SLA restated a severity target"
    assert "1-hour response" not in doc
    assert "2-hour restore" not in doc


def test_sla_blocks_its_own_external_use_until_fnd_064_is_reconciled():
    """The dependency is a gate, not a footnote."""
    doc = _sla()
    assert "FND-064" in doc
    assert "must not be issued" in doc.lower()


# ── The finding itself ──────────────────────────────────────────────────────


def test_fnd_064_is_logged_as_open():
    ledger = FINDINGS.read_text(encoding="utf-8")
    assert "FND-064" in ledger, "IR-plan contradiction must be in the findings ledger"
    row = [ln for ln in ledger.splitlines() if ln.startswith("| FND-064 ")][0]
    assert row.rstrip().endswith("| open |"), "FND-064 should be open (STORY-371 owns the fix)"


def test_fnd_064_records_the_external_exposure():
    """The reason this matters is that a customer can already read it."""
    ledger = FINDINGS.read_text(encoding="utf-8")
    row = [ln for ln in ledger.splitlines() if ln.startswith("| FND-064 ")][0]
    assert "governance/ir-plan" in row
    assert "sla_hours" in row


def test_ir_plan_still_contains_the_unreconciled_claims():
    """Guards against the finding being closed by deletion rather than decision.

    If someone edits these claims out, this test fails and forces the change to
    be made deliberately — updating FND-064 and the SLA gate along with it.
    """
    irp = (ROOT / "docs" / "incident-response-plan.md").read_text(encoding="utf-8")
    unreconciled = ("Automated (<5 min)" in irp) or ("0–5 min" in irp) or ("@oncall" in irp)
    assert unreconciled, (
        "the IR plan's contested claims appear to have changed — reconcile "
        "FND-064 and docs/legal/sla-draft-v0.1.md §5 in the same change"
    )
