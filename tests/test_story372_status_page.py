"""STORY-372 — status page and degradation communication.

A status page's failure mode is stating the opposite of the truth during an
outage, so these tests are mostly about what it must never claim.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.unit

STATUS = ROOT / "frontend" / "public" / "status.html"
PROC = ROOT / "docs" / "ops" / "maintenance-windows.md"
SLA = ROOT / "docs" / "legal" / "sla-draft-v0.1.md"


def _page() -> str:
    return STATUS.read_text(encoding="utf-8")


# ── AC-1: the page exists and is genuinely live ─────────────────────────────


def test_status_page_exists_where_vite_will_publish_it():
    assert STATUS.exists()
    assert STATUS.parent.name == "public", "Vite copies publicDir into dist"


def test_page_probes_health_live_rather_than_reading_a_cached_file():
    """A cached banner can say 'operational' during an outage."""
    page = _page()
    assert 'fetch("/health"' in page
    assert 'cache: "no-store"' in page
    assert "setInterval" in page, "the page should re-check without a reload"


def test_page_has_no_external_dependencies():
    """It must keep working when everything else does not."""
    page = _page()
    assert not re.search(r'src\s*=\s*["\']https?://', page), "external script"
    assert not re.search(r'href\s*=\s*["\']https?://[^"\']*\.css', page), "external stylesheet"


def test_no_hardcoded_operational_claim_in_markup():
    """The word must only ever be produced by a successful probe."""
    page = _page()
    markup = page[: page.index("<script")]
    assert "Operational" not in markup, (
        "status text appears in static markup — it would show during an outage"
    )
    assert "Checking…" in markup, "initial state should be unknown, not healthy"


# ── What it must never claim ────────────────────────────────────────────────


def test_fetch_failure_reports_down_not_unknown_healthy():
    page = _page()
    start = page.index("} catch (err) {") + len("} catch (err) {")
    catch_block = page[start : page.index("}", start)]
    assert catch_block.strip(), "could not isolate the catch block"
    assert catch_block.count('"down"') == 2, "both API and DB must render down"
    assert '"ok"' not in catch_block, "a failed probe must never paint a healthy state"


def test_503_is_reported_as_degraded_not_a_hard_outage():
    """503 is the documented healthy-process/unhealthy-dependency response."""
    page = _page()
    assert "degraded" in page
    assert "Responding with" in page


def test_missing_db_flag_is_reported_as_unknown_not_healthy():
    page = _page()
    assert "Not reported by this response" in page


def test_db_false_states_the_user_visible_consequence():
    assert "evaluations will fail" in _page()


# ── AC-2 / honesty: the limitation is on the page itself ────────────────────


def test_page_discloses_that_it_shares_fate_with_the_frontend():
    page = _page()
    assert "not an independent monitor" in page.lower()
    assert "frontend" in page.lower()


def test_procedure_documents_the_independent_hosting_gap_as_human_gated():
    doc = PROC.read_text(encoding="utf-8")
    assert "[HUMAN — OPEN]" in doc
    assert "independent" in doc.lower()


# ── AC-2: announcement procedure ────────────────────────────────────────────


def test_procedure_states_notice_period_and_window():
    doc = PROC.read_text(encoding="utf-8")
    assert "72 hours" in doc
    assert "02:00–04:00 UTC" in doc


def test_procedure_covers_unplanned_degradation_not_only_maintenance():
    doc = PROC.read_text(encoding="utf-8")
    assert "unplanned degradation" in doc.lower()
    assert "hourly" in doc.lower(), "update cadence during an open incident"


def test_procedure_forbids_the_dishonest_moves():
    """The failure modes that cost trust rather than uptime."""
    doc = PROC.read_text(encoding="utf-8").lower()
    assert "do not" in doc
    assert "retroactively" in doc, "backdating maintenance to cover an outage"
    assert "has not been verified" in doc


def test_procedure_defers_to_the_irp_when_evidence_is_involved():
    doc = PROC.read_text(encoding="utf-8")
    assert "incident response plan" in doc.lower()
    assert "evidence integrity" in doc.lower()


# ── AC-3: linked from the SLA ───────────────────────────────────────────────


def test_sla_links_the_procedure_and_the_status_page():
    doc = SLA.read_text(encoding="utf-8")
    assert "maintenance-windows.md" in doc
    assert "status.html" in doc


def test_sla_repeats_the_independence_caveat():
    """A buyer reading only the SLA must still learn the limitation."""
    # Whitespace collapsed: the prose is hard-wrapped, so the phrase straddles a
    # newline. Matching raw text would make this hostage to line breaks.
    doc = re.sub(r"\s+", " ", SLA.read_text(encoding="utf-8")).lower()
    assert "not an independent monitor" in doc
