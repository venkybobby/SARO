"""STORY-412: demo surface trim — every DEMO_TABS endpoint must survive a click.

Mints a real demo JWT via `GET /api/v1/demo/token` (the same endpoint
DemoEntry.jsx calls) and asserts every GET each DEMO_TABS page fires on load
returns 200 (AC-1), and that a write attempt with the same token still 403s
(AC-4, regression-pinning existing `require_write_access` behavior).

The DEMO_TABS whitelist itself is loaded from `frontend/src/config/
demoTabs.json` — the same file Sidebar.jsx imports — so the frontend
whitelist and this backend census cannot silently drift apart (AC-1's own
requirement).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from middleware import rate_limiter
from models import Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT_ID = uuid.uuid4()


def _seed() -> None:
    db = _Session()
    db.add(Tenant(id=TENANT_ID, name="STORY-412 demo census tenant", slug="story412-demo"))
    db.commit()
    db.close()


_seed()

_DEMO_TABS_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend" / "src" / "config" / "demoTabs.json"
)
DEMO_TABS: list[str] = json.loads(_DEMO_TABS_PATH.read_text())

# Every GET each DEMO_TABS page fires on load, cited file:line in
# implementation-notes.md's Discover section:
#   dashboard:       Dashboard.jsx: risk/summary, risk/whats-changed, drift-alerts
#                      (STORY-412) + audits/compliance-matrix-coverage, wired by
#                      STORY-413's useAuditsLast7d/useCoveragePct hooks once that
#                      story landed — kept in sync here per round-2 reviewer finding.
#   trace_view:       TraceView.jsx:157 (recent-list — the only on-mount GET;
#                      detail fetches only fire after a user picks an audit)
#   compliance_hub:   ComplianceHub.jsx loadCoverage/loadStatuses/loadAudits/
#                      loadReadiness + ComplianceCalendar's qco/expiry-alerts
#   reports:          Reports.jsx:102 (the ONLY GET this page fires — it does
#                      not call any /api/v1/reports/* endpoint)
_TAB_ENDPOINTS: dict[str, list[str]] = {
    "dashboard": [
        "/api/v1/risk/summary",
        "/api/v1/risk/whats-changed",
        "/api/v1/rules/drift-alerts",
        "/api/v1/audits?limit=200",
        "/api/v1/compliance-matrix/coverage",
    ],
    "trace_view": [
        "/api/v1/audits?limit=10&sort=desc",
    ],
    "compliance_hub": [
        "/api/v1/compliance-matrix/coverage",
        "/api/v1/evf/validation-status",
        "/api/v1/evf/qco/expiry-alerts?limit=20",
        "/api/v1/audits?limit=10",
        "/api/v1/compliance/readiness",
    ],
    "reports": [
        "/api/v1/risks",
    ],
}


def _client() -> TestClient:
    app.dependency_overrides[get_db] = lambda: _Session()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def demo_token(monkeypatch) -> str:
    monkeypatch.setenv("SARO_DEMO_TENANT_ID", str(TENANT_ID))
    # FND-090 made /api/v1/demo/token subject to the strict per-IP rate limit.
    # This census mints a fresh token per test via the real main.app, which
    # would otherwise share a live Redis bucket with every other test hitting
    # an _AUTH_STRICT_PREFIXES route in the same run.
    monkeypatch.setattr(
        rate_limiter,
        "check_rate_limit",
        lambda key, limit: {"allowed": True, "count": 0, "limit": limit,
                             "remaining": limit, "retry_after": 1, "reset_epoch": 0},
    )
    r = _client().get("/api/v1/demo/token")
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_demo_tabs_fixture_matches_the_endpoint_census():
    """AC-1 precondition: the JSON fixture Sidebar.jsx reads is exactly the
    whitelist this census covers — catches the two from drifting apart."""
    assert set(DEMO_TABS) == set(_TAB_ENDPOINTS)


@pytest.mark.parametrize("tab", DEMO_TABS)
def test_demo_token_grants_200_on_every_tab_endpoint(demo_token, tab):
    """AC-1: every GET a DEMO_TABS page fires on load returns 200, not 401/403."""
    client = _client()
    headers = {"Authorization": f"Bearer {demo_token}"}
    for endpoint in _TAB_ENDPOINTS[tab]:
        r = client.get(endpoint, headers=headers)
        assert r.status_code == 200, f"{tab} -> {endpoint} returned {r.status_code}: {r.text}"


def test_demo_token_write_access_still_forbidden(demo_token):
    """AC-4: a demo token still cannot write — regression-pins the existing
    require_write_access behavior (not new behavior)."""
    client = _client()
    headers = {"Authorization": f"Bearer {demo_token}"}
    r = client.post(
        "/api/v1/ingest",
        headers=headers,
        json={"prompt": "x", "raw_output": "y"},
    )
    assert r.status_code == 403, r.text


def test_demo_token_cannot_toggle_readiness_item(demo_token):
    """AC-4: the one write action a DEMO_TABS page actually renders — the
    ComplianceHub readiness checklist toggle (ComplianceHub.jsx:413-419) —
    still 403s. require_write_persona checks read_only before persona, and
    the demo synthetic user is always read_only=True (auth.py:186)."""
    client = _client()
    headers = {"Authorization": f"Bearer {demo_token}"}
    r = client.put(
        "/api/v1/compliance/readiness/some-item-key",
        headers=headers,
        json={"completed": True},
    )
    assert r.status_code == 403, r.text
