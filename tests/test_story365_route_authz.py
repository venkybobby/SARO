"""STORY-365 — route-authorization probe suite (INV-3 regression guard).

Auto-discovers every registered API route and probes it WITHOUT credentials.
Every route must either reject the request (401/403) or be listed in
PUBLIC_ROUTES with a justification. A newly added route that forgets auth
fails this suite by default — that is the point.

Also pins the STORY-365 hardening pass: security headers on responses and the
scoped per-IP rate limits (auth + evaluate prefixes).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

from _route_utils import iter_api_routes  # noqa: E402

pytestmark = pytest.mark.integration

# ── Public-by-design routes (method, path) — every entry needs a reason ──────
PUBLIC_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/"): "root banner — no data",
    ("GET", "/health"): "release-gate health probe",
    ("POST", "/api/v1/auth/token"): "login endpoint",
    ("POST", "/api/v1/auth/register"): "registration endpoint (gated in-route)",
    ("POST", "/api/v1/auth/bootstrap"): "first-run bootstrap — self-disables after first admin",
    ("GET", "/api/v1/demo/token"): "demo-mode token issuance (feature-flagged)",
    ("GET", "/api/v1/version"): (
        "running version — a customer's change-management process must read it "
        "without a credential; reports version + build commit, no tenant data (STORY-375)"
    ),
    ("POST", "/api/v1/demo/signup"): "public demo-request intake (feature-flagged)",
    ("POST", "/api/v1/sso/magic-link"): "magic-link request — rate-limited per IP",
    ("GET", "/api/v1/remediation/oauth/jira/callback"): (
        "OAuth provider redirect — no JWT by design. Authenticity comes from the "
        "HMAC-signed single-use state param (TM-F1/FND-061, b82755b), not from a "
        "bearer token: the tenant binding is verified, not asserted."
    ),
}
# Prefixes that are public-by-design as a family.
PUBLIC_PREFIXES: dict[str, str] = {
    "/api/v1/sso/": "IdP-initiated SSO handshake — signature-verified in-route",
}

_DUMMY_PARAMS = {
    "int": "1",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "default": "probe",
}


def _fill_path(route: APIRoute) -> str:
    path = route.path
    for name, conv in route.param_convertors.items():
        klass = type(conv).__name__.lower()
        if "uuid" in klass:
            value = _DUMMY_PARAMS["uuid"]
        elif "int" in klass:
            value = _DUMMY_PARAMS["int"]
        else:
            value = _DUMMY_PARAMS["default"]
        path = path.replace("{%s}" % name, value)
    return path


def _api_routes() -> list[tuple[str, APIRoute]]:
    out = []
    for route in iter_api_routes(app):  # FND-069: recurse; Starlette may nest routers
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            out.append((method, route))
    return out


@pytest.fixture(scope="module")
def client():
    # No context manager: startup events run Postgres DDL migrations, which the
    # probe neither needs nor can satisfy locally (repo-wide test convention).
    yield TestClient(app, raise_server_exceptions=False)


def test_every_route_rejects_unauthenticated_requests(client):
    """The core probe: no credentials → 401/403 on everything non-public."""
    unprotected: list[str] = []
    for method, route in _api_routes():
        key = (method, route.path)
        if key in PUBLIC_ROUTES:
            continue
        if any(route.path.startswith(p) for p in PUBLIC_PREFIXES):
            continue
        url = _fill_path(route)
        resp = client.request(method, url)
        if resp.status_code not in (401, 403):
            unprotected.append(f"{method} {route.path} -> {resp.status_code}")
    assert not unprotected, (
        "routes reachable without credentials (add auth, or add to PUBLIC_ROUTES "
        "with a justification):\n  " + "\n  ".join(unprotected)
    )


def test_public_allowlist_has_no_stale_entries():
    """Every allowlisted route must still exist — dead entries hide regressions."""
    known = {(m, r.path) for m, r in _api_routes()}
    stale = [k for k in PUBLIC_ROUTES if k not in known]
    assert not stale, f"PUBLIC_ROUTES entries no longer registered: {stale}"


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert "default-src 'none'" in resp.headers.get("Content-Security-Policy", "")


def test_docs_csp_is_relaxed_not_absent(client):
    resp = client.get("/docs")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp, "docs page needs its own CSP, not the deny-all one"


def test_rate_limiter_scopes_evaluate_prefixes():
    from middleware import rate_limiter as rl

    assert "/api/v1/scan" in rl._EVALUATE_PREFIXES
    assert "/api/v1/ingest" in rl._EVALUATE_PREFIXES
    assert rl._EVALUATE_RATE_LIMIT_RPM > 0
