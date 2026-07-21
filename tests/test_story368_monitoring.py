"""STORY-368 — platform monitoring, alerting, and the synthetic canary.

The load-bearing tests are the ones about what metrics must NOT contain. A
scrape endpoint is a quiet way to leak the customer list, so tenant labels are
asserted absent rather than merely avoided by convention.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import services.metrics as metrics  # noqa: E402
from main import app  # noqa: E402

pytestmark = pytest.mark.integration

ALERTS = ROOT / "docs" / "ops" / "alerts.md"
RUNBOOKS = ROOT / "docs" / "ops" / "runbooks.md"
CANARY_WF = ROOT / ".github" / "workflows" / "canary.yml"
CANARY_SCRIPT = ROOT / "scripts" / "canary_evaluation.py"

_TOKEN = "canary-test-token-value"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", _TOKEN)
    yield _TOKEN


# ── AC-1: the endpoints ─────────────────────────────────────────────────────


def test_metrics_route_is_registered():
    from fastapi.routing import APIRoute

    assert any(isinstance(r, APIRoute) and r.path == "/metrics" for r in app.routes)


def test_metrics_requires_a_token(client, token_env):
    assert client.get("/metrics").status_code == 401


def test_metrics_rejects_a_wrong_token(client, token_env):
    resp = client.get("/metrics", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_metrics_is_closed_when_no_token_is_configured(client, monkeypatch):
    """Fail closed: unconfigured must not mean open (the CORS anti-pattern)."""
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer anything"}).status_code == 401


def test_health_endpoint_still_serves_the_documented_contract(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)
    body = resp.json()
    for field in ("status", "db_ok"):
        assert field in body, f"/health lost the {field!r} field the canary depends on"


# ── INV-3: no tenant identifiers in a scrape ────────────────────────────────


def test_exposition_carries_no_tenant_labels():
    """A tenant label set would disclose the customer list to any scraper.

    Checked on the METRIC lines only: `# HELP` comments legitimately contain the
    word "tenant" while stating that no tenant labels exist, and failing on that
    would punish the documentation for describing the guarantee.
    """
    metrics.reset_for_tests()
    metrics.observe_request("GET", 200, 0.05)
    metric_lines = [
        ln for ln in metrics.render_exposition(version="test").splitlines()
        if ln and not ln.startswith("#")
    ]
    assert metric_lines, "exposition produced no metric lines"
    for line in metric_lines:
        lowered = line.lower()
        for forbidden in ("tenant", "customer", "email", "user_id", "@"):
            assert forbidden not in lowered, f"metric line leaked {forbidden!r}: {line}"


def test_request_metric_labels_exclude_the_path():
    """Raw paths carry ids — high cardinality and customer-identifying."""
    metrics.reset_for_tests()
    metrics.observe_request("GET", 200, 0.01)
    text = metrics.render_exposition()
    assert 'path=' not in text
    assert 'status="2xx"' in text
    assert 'method="GET"' in text


def test_observe_request_records_status_class_not_exact_code():
    metrics.reset_for_tests()
    metrics.observe_request("POST", 503, 0.2)
    assert metrics.REQUESTS.value(method="POST", status="5xx") == 1
    assert metrics.REQUESTS.value(method="POST", status="503") == 0


# ── Exposition format ───────────────────────────────────────────────────────


def test_exposition_is_valid_prometheus_text():
    metrics.reset_for_tests()
    metrics.observe_request("GET", 200, 0.3)
    text = metrics.render_exposition(version="1.2.3")
    assert "# HELP saro_http_requests_total" in text
    assert "# TYPE saro_http_requests_total counter" in text
    assert "saro_http_request_duration_seconds_bucket{le=\"+Inf\"}" in text
    assert "saro_http_request_duration_seconds_count 1" in text
    # every non-comment line must be `name{labels} value`
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        assert re.match(r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{.*\})? -?[0-9.eE+-]+$", line), line


def test_histogram_buckets_are_cumulative():
    metrics.reset_for_tests()
    for value in (0.05, 0.4, 3.0):
        metrics.REQUEST_DURATION.observe(value)
    text = "\n".join(metrics.REQUEST_DURATION.render())
    assert 'le="0.1"} 1' in text
    assert 'le="0.5"} 2' in text
    assert 'le="5"} 3' in text


def test_unknown_ingestion_lag_is_minus_one_not_zero():
    """-1 means 'no checkpoints yet'. Zero would read as perfectly fresh."""
    metrics.reset_for_tests()
    metrics.INGESTION_LAG.set(-1)
    assert "saro_ingestion_lag_seconds -1" in metrics.render_exposition()


def test_metrics_scrape_succeeds_with_a_valid_token(client, token_env):
    resp = client.get("/metrics", headers={"Authorization": f"Bearer {_TOKEN}"})
    # 200 with the exposition, or 503 if the DB dependency is unavailable in
    # this environment — either way, never a 500 and never unauthenticated data.
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert "saro_http_requests_total" in resp.text
        assert "text/plain" in resp.headers["content-type"]


# ── AC-2: documented thresholds with justification ──────────────────────────


def test_alert_doc_defines_thresholds_with_numbers():
    doc = ALERTS.read_text(encoding="utf-8")
    assert "5400" in doc, "ingestion lag threshold missing"
    assert "90 minutes" in doc or "**90 minutes**" in doc
    assert "5%" in doc, "error-rate threshold missing"
    for alert_id in ("A1", "A2", "A3", "A4", "A5", "A6"):
        assert alert_id in doc, f"{alert_id} not documented"


def test_every_threshold_carries_a_justification():
    doc = ALERTS.read_text(encoding="utf-8")
    assert doc.lower().count("why") >= 5, "thresholds are stated without reasons"


def test_alert_doc_states_the_counter_reset_caveat():
    """A counter read as a lifetime total produces false alerts."""
    doc = ALERTS.read_text(encoding="utf-8").lower()
    assert "reset on restart" in doc


# ── AC-3: delivery channel chosen and its weakness stated ───────────────────


def test_delivery_channel_is_documented_with_its_limitation():
    doc = ALERTS.read_text(encoding="utf-8")
    assert "GitHub Actions failure notifications" in doc
    assert "email is not a pager" in doc.lower(), (
        "the channel's weakness must be stated, not glossed"
    )
    assert "[HUMAN — OPEN]" in doc


# ── AC-4: the canary ────────────────────────────────────────────────────────


def test_canary_workflow_exists_and_is_scheduled():
    import yaml

    wf = yaml.safe_load(CANARY_WF.read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)  # PyYAML parses bare `on:` as True
    assert "schedule" in on
    assert on["schedule"][0]["cron"] == "*/30 * * * *"


def test_canary_checks_health_lag_and_an_evaluation():
    text = CANARY_WF.read_text(encoding="utf-8")
    assert "/health" in text
    assert "saro_ingestion_lag_seconds" in text
    assert "canary_evaluation.py" in text


def test_canary_treats_unknown_lag_as_not_an_incident():
    text = CANARY_WF.read_text(encoding="utf-8")
    assert "not an incident" in text


def test_canary_reports_when_the_evaluation_is_skipped():
    """Missing credentials must warn loudly, never pass as if it ran."""
    text = CANARY_WF.read_text(encoding="utf-8")
    assert "::warning::canary evaluation SKIPPED" in text


def test_canary_script_asserts_contract_not_an_exact_score():
    """Pinning a score would make every scoring change look like an outage."""
    src = CANARY_SCRIPT.read_text(encoding="utf-8")
    assert "0 <= score_value <= 100" in src
    assert "never an exact score" in src


def test_canary_sample_contains_no_phi():
    from canary_evaluation import CANARY_OUTPUT, CANARY_PROMPT  # noqa: E402

    combined = f"{CANARY_PROMPT} {CANARY_OUTPUT}".lower()
    for marker in ("mrn", "ssn", "patient name", "dob"):
        assert marker not in combined


def test_canary_failures_point_at_a_runbook():
    src = CANARY_SCRIPT.read_text(encoding="utf-8")
    assert "runbook" in src.lower()
    wf = CANARY_WF.read_text(encoding="utf-8")
    assert "docs/ops/runbooks.md" in wf


# ── AC-5: a runbook per alert ───────────────────────────────────────────────


def test_runbook_exists_for_every_alert():
    doc = RUNBOOKS.read_text(encoding="utf-8")
    for alert_id in ("A1", "A2", "A3", "A4", "A5", "A6", "A7"):
        assert f"## {alert_id}" in doc, f"no runbook section for {alert_id}"


def test_each_runbook_gives_a_first_command_and_causes():
    doc = RUNBOOKS.read_text(encoding="utf-8")
    assert doc.count("**First command**") >= 5
    assert doc.count("Likely cause") >= 5


def test_runbooks_preserve_evidence_integrity_priority():
    """Restoring service fast must not outrank protecting the audit chain."""
    doc = RUNBOOKS.read_text(encoding="utf-8").lower()
    assert "evidence integrity" in doc


sys.path.insert(0, str(ROOT / "scripts"))
