"""Live demo E2E flow — automates RB-006 §§A–E + §H for the UC-1..UC-5 demo.

The planned demo runs on the public ``/demo`` flow (DemoEntry.jsx auto-mints the
demo JWT and renders the DEMO_TABS surface: Dashboard, TRACE View, Compliance
Hub, Reports). The demo corpus (scripts/demo_manifest.yaml) plants five use
cases; UC-1 (PHI leakage), UC-2 (hallucinated clinical guidance) and UC-5
(off-allowlist model → ENV-MODEL-ALLOWLIST-1) are expected to FIRE, while UC-3
and UC-4 are planted-pending-rule and are deliberately NOT asserted as findings.

Run (RB-006 T-24h and T-1h):

    SARO_LIVE_E2E=1 pytest tests/e2e -m e2e -q

Section map (test name prefix → RB-006 section):
    test_a_*  §A backend reachability + demo token claims
    test_b_*  §B demo-tab endpoint census (same list as STORY-412's CI census)
    test_c_*  §C seeded data present
    test_d_*  §D UC exemplars fire live (UC-5 ENV-MODEL-ALLOWLIST-1 is the gate)
    test_e_*  §E read-only enforcement (negative)
    test_h_*  §H browser pass (Playwright walk of /demo)

§F (fly ssh env hygiene) and §G (credential rotation) are operator checks that
need fly.io access and stay manual.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# CI's unit/integration/regression jobs install only requirements.txt —
# playwright lives solely in the dedicated e2e job. Skip at collection time so
# `pytest tests/` stays collectable everywhere.
_playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="playwright not installed — live demo gate runs only where the e2e deps exist",
)

if TYPE_CHECKING:
    from playwright.sync_api import Page, expect
else:
    Page = _playwright.Page
    expect = _playwright.expect

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("SARO_LIVE_E2E") != "1",
        reason="live demo gate — set SARO_LIVE_E2E=1 to run against the deployed apps",
    ),
]


def decode_jwt_payload(token: str) -> dict:
    """Decode a JWT payload without verifying the signature (claims-shape checks only)."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


RESEED_HINT = (
    "Demo tenant has no audits — RB-006 §C: reseed the live demo tenant "
    "(python cli.py demo reset --tenant <demo_tenant_id> --yes, then re-ingest "
    "the STORY-407 corpus per the operator runbook) before any external demo."
)

# RB-006 §B census — this is the runbook's exact 10-endpoint list, verbatim.
# tests/regression/test_story_412_demo_tab_endpoint_census.py pins the same
# ROUTES against the in-process app but with the frontend's own query params
# (limit=200/limit=10, per-tab duplicates); authz coverage is equivalent, the
# literals are not. Edit RB-006 and this list together.
CENSUS_ENDPOINTS = [
    "/api/v1/risk/summary",
    "/api/v1/risk/whats-changed",
    "/api/v1/rules/drift-alerts",
    "/api/v1/audits?limit=5",
    "/api/v1/compliance-matrix/coverage",
    "/api/v1/audits?limit=10&sort=desc",
    "/api/v1/evf/validation-status",
    "/api/v1/evf/qco/expiry-alerts?limit=20",
    "/api/v1/compliance/readiness",
    "/api/v1/risks",
]

# Sidebar labels for each DEMO_TABS id (Sidebar.jsx NAV definitions).
TAB_LABELS = {
    "dashboard": "Dashboard",
    "trace_view": "TRACE View",
    "compliance_hub": "Compliance Hub",
    "reports": "Reports",
}

DEMO_TABS_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "config"
    / "demoTabs.json"
)
DEMO_TABS: list[str] = json.loads(DEMO_TABS_PATH.read_text())


def _audits(api, auth_headers, limit=50) -> list[dict]:
    r = api.get(f"/api/v1/audits?limit={limit}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    return body if isinstance(body, list) else body.get("items", [])


# ---------------------------------------------------------------- §A ---------


def test_a_health(api):
    r = api.get("/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("db_ok") is True, f"backend up but DB unhealthy: {body}"
    assert not body.get("missing_migrations"), (
        f"deployed schema is behind: missing {body['missing_migrations']}"
    )


def test_a_demo_token_claims(demo_token):
    """The demo JWT must be read-only and carry the compliance_lead persona —
    DemoEntry.jsx builds the whole demo session from these claims."""
    claims = decode_jwt_payload(demo_token)
    assert claims.get("read_only") is True, f"demo token is NOT read-only: {claims}"
    assert claims.get("role") == "demo_viewer", claims
    assert claims.get("persona_role") == "compliance_lead", claims
    assert claims.get("tenant_id") or claims.get("sub"), (
        f"no tenant identity in demo token: {claims}"
    )


# ---------------------------------------------------------------- §B ---------


@pytest.mark.parametrize("endpoint", CENSUS_ENDPOINTS)
def test_b_census_endpoint_returns_200(api, auth_headers, endpoint):
    r = api.get(endpoint, headers=auth_headers)
    assert r.status_code == 200, (
        f"{endpoint} -> {r.status_code}. RB-006 §B: 403 = STORY-412 whitelist "
        f"violation; 500 = stop, fix before demo. A mismatch with green CI means "
        f"the deployed build is behind main. Body: {r.text[:300]}"
    )


# ---------------------------------------------------------------- §C ---------


def test_c_seeded_audits_present(api, auth_headers):
    audits = _audits(api, auth_headers, limit=5)
    assert audits, RESEED_HINT


def test_c_risk_scores_are_probabilities(api, auth_headers):
    """FND-059 live guard: stored overall_risk_score is the engine's 0–1
    probability; a value > 1 means the buggy pre-FND-059 seeder wrote this
    tenant and the frontend will render '1286/100' badges."""
    audits = _audits(api, auth_headers, limit=50)
    if not audits:
        pytest.fail(RESEED_HINT)
    bad = [
        (a.get("id"), a.get("overall_risk_score"))
        for a in audits
        if isinstance(a.get("overall_risk_score"), (int, float))
        and a["overall_risk_score"] > 1.0
    ]
    assert not bad, (
        f"audits carry pre-scaled risk scores (>1.0) — reseed with the fixed "
        f"seeder (FND-059): {bad[:5]}"
    )


# ---------------------------------------------------------------- §D ---------


def test_d_uc5_model_allowlist_finding_fires_live(api, auth_headers):
    """The marquee governance moment: the UC-5 audit (off-allowlist
    anthropic.claude-instant-v1 invocation) must surface ENV-MODEL-ALLOWLIST-1
    in its trace. RB-006 §D: do not demo UC-5 until this passes."""
    audits = _audits(api, auth_headers, limit=50)
    if not audits:
        pytest.fail(RESEED_HINT)
    searched = []
    for a in audits:
        audit_id = a.get("id") or a.get("audit_id")
        r = api.get(f"/api/v1/audit/{audit_id}/trace", headers=auth_headers)
        if r.status_code != 200:
            continue
        searched.append(audit_id)
        if "ENV-MODEL-ALLOWLIST-1" in r.text:
            return
    pytest.fail(
        f"ENV-MODEL-ALLOWLIST-1 absent from all {len(searched)} trace(s) — the "
        "UC-5 exemplar is not firing live (STORY-411 merged-only?). "
        "Re-ingest the demo corpus and re-verify."
    )


def test_d_uc1_uc2_exemplars_present_live(api, auth_headers):
    """UC-1 (PHI leakage → Privacy & Security) and UC-2 (hallucinated clinical
    guidance → Misinformation) are 'expected: fires' in demo_manifest.yaml —
    their domains must appear somewhere in the demo tenant's traces."""
    audits = _audits(api, auth_headers, limit=50)
    if not audits:
        pytest.fail(RESEED_HINT)
    corpus_text = []
    for a in audits:
        audit_id = a.get("id") or a.get("audit_id")
        r = api.get(f"/api/v1/audit/{audit_id}/trace", headers=auth_headers)
        if r.status_code == 200:
            corpus_text.append(r.text.lower())
    blob = " ".join(corpus_text)
    missing = [
        uc
        for uc, needle in [
            ("UC-1 (PHI/privacy)", "privacy"),
            ("UC-2 (misinformation)", "misinformation"),
        ]
        if needle not in blob
    ]
    assert not missing, (
        f"firing use-case exemplar(s) absent from all live traces: {missing} — "
        "the demo corpus is not (fully) ingested."
    )


# ---------------------------------------------------------------- §E ---------


def test_e_demo_token_cannot_ingest(api, auth_headers):
    # Sentinel body: if the guard were ever broken, the one junk record this
    # probe writes is identifiable and cleanable in the demo tenant.
    r = api.post(
        "/api/v1/ingest",
        headers=auth_headers,
        json={
            "prompt": "SARO-E2E-READONLY-PROBE",
            "raw_output": "SARO-E2E-READONLY-PROBE (RB-006 §E negative test)",
        },
    )
    assert r.status_code == 403, (
        f"POST /api/v1/ingest with the PUBLIC demo token returned {r.status_code} "
        "— RB-006 §E: a 2xx means the demo token can WRITE. Stop everything and fix."
    )


def test_e_demo_token_cannot_toggle_readiness(api, auth_headers):
    r = api.put(
        "/api/v1/compliance/readiness/some-item-key",
        headers=auth_headers,
        json={"completed": True},
    )
    assert r.status_code == 403, (
        f"readiness toggle returned {r.status_code} — the one write button a demo "
        "visitor can click (ComplianceHub checklist) must 403."
    )


# ---------------------------------------------------------------- §H ---------


def _watch_api_failures(page: Page) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    page.on(
        "response",
        lambda r: (
            bad.append((r.status, r.url))
            if "/api/" in r.url and r.status >= 400
            else None
        ),
    )
    return bad


def _open_demo(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/demo", wait_until="networkidle", timeout=60_000)
    # DemoEntry renders the AppShell once the token lands; "Demo unavailable"
    # is its terminal error card.
    assert not page.get_by_text("Demo unavailable").is_visible(), (
        "/demo shows the 'Demo unavailable' error card — token fetch failed in-browser "
        "(check ALLOWED_ORIGINS / nginx /api proxy)."
    )
    page.get_by_text("Dashboard", exact=True).first.wait_for(timeout=30_000)


def test_h_demo_entry_renders_dashboard(page: Page, frontend_url, artifact_dir):
    bad = _watch_api_failures(page)
    _open_demo(page, frontend_url)
    page.screenshot(path=str(artifact_dir / "01-demo-entry.png"), full_page=True)
    assert not bad, f"API responses >= 400 on /demo entry: {bad}"


def test_h_sidebar_health_badge_is_online(page: Page, frontend_url):
    """FND-060 live guard: the sidebar /health poll must resolve through the
    nginx proxy — a red 'API offline' badge in front of attendees was F2."""
    _open_demo(page, frontend_url)
    # Wait for the poll to resolve to the positive state ("API online · DB ok")
    # instead of sleeping a fixed beat — a slow first /health response would
    # otherwise make the offline check pass vacuously.
    expect(page.get_by_text("API online", exact=False)).to_be_visible(timeout=15_000)
    assert page.get_by_text("API offline").count() == 0, (
        "Sidebar shows 'API offline' — frontend/nginx.conf /health proxy fix "
        "(FND-060) is not live; redeploy sarofrontend."
    )


def test_h_tab_walk_zero_red_rows(page: Page, frontend_url, artifact_dir):
    """RB-006 §H: click every DEMO_TABS tab with the network watched — zero
    API responses >= 400, no 'sample' captions, and no risk badge above 100."""
    bad = _watch_api_failures(page)
    _open_demo(page, frontend_url)
    failures: list[str] = []
    for i, tab in enumerate(DEMO_TABS, start=2):
        label = TAB_LABELS.get(tab, tab)
        try:
            page.get_by_text(label, exact=True).first.click(timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
            page.wait_for_timeout(1_000)
            page.screenshot(
                path=str(artifact_dir / f"{i:02d}-{tab}.png"), full_page=True
            )
            body = page.inner_text("body")
            if "sample — not yet wired" in body:
                failures.append(
                    f"{tab}: STORY-413 'sample' caption visible — deployed build is stale"
                )
            # F1 guard: any "N/100" badge must be a sane 0–100 integer.
            for m in re.finditer(r"(\d+)\s*/\s*100\b", body):
                if int(m.group(1)) > 100:
                    failures.append(
                        f"{tab}: risk badge reads {m.group(0)} — double-scaling (F1/FND-059)"
                    )
        except Exception as exc:  # noqa: BLE001 — record and keep walking
            page.screenshot(path=str(artifact_dir / f"{i:02d}-{tab}-FAILED.png"))
            failures.append(f"{tab}: {exc}")
    assert not failures, "tab walk failures:\n" + "\n".join(failures)
    assert not bad, f"API responses >= 400 during tab walk: {bad}"


def test_h_trace_detail_opens(page: Page, frontend_url, artifact_dir):
    """RB-006 §H: open one TRACE detail from the Recent Traces chips and see
    the timeline render (the chips are the id-prefix buttons, e.g. 'a1b2c3d4…')."""
    bad = _watch_api_failures(page)
    _open_demo(page, frontend_url)
    page.get_by_text(TAB_LABELS["trace_view"], exact=True).first.click()
    page.wait_for_load_state("networkidle", timeout=30_000)
    chips = page.locator("button:has-text('…')")
    if chips.count() == 0:
        pytest.fail(RESEED_HINT + " (no Recent Traces chips rendered on TRACE View)")
    chips.first.click(timeout=10_000)
    page.wait_for_load_state("networkidle", timeout=30_000)
    page.wait_for_timeout(1_500)
    page.screenshot(path=str(artifact_dir / "06-trace-detail.png"), full_page=True)
    assert not bad, f"API responses >= 400 opening TRACE detail: {bad}"


def test_h_hard_refresh_reauthenticates(page: Page, frontend_url):
    """RB-006 §H: the demo JWT is React-state-held (never localStorage), so a
    hard refresh must silently re-mint the token and land back on the shell."""
    _open_demo(page, frontend_url)
    page.reload(wait_until="networkidle", timeout=60_000)
    page.get_by_text("Dashboard", exact=True).first.wait_for(timeout=30_000)
    # Scan KEYS and VALUES of both web storages: a JWT hidden under an
    # innocuous key (or in sessionStorage) must still trip this. JWT segments
    # always start with "eyJ" (base64 of '{"').
    token_in_storage = page.evaluate(
        """() => {
          const hits = [];
          for (const store of [localStorage, sessionStorage]) {
            for (let i = 0; i < store.length; i++) {
              const k = store.key(i);
              const v = store.getItem(k) || "";
              if (/token|jwt/i.test(k) || v.includes("eyJ")) hits.push(k);
            }
          }
          return hits;
        }"""
    )
    assert not token_in_storage, (
        f"demo JWT appears to be persisted in web storage (keys: {token_in_storage}) — "
        "DemoEntry.jsx's CRITICAL invariant is state-held-only."
    )
