"""FND-060: deployed frontend showed a permanent red "API offline" badge.

Sidebar.jsx polls ``fetch("/health")`` every 30s, but frontend/nginx.conf proxied
only ``location /api/`` — ``/health`` fell through to the SPA fallback and returned
index.html with a 200, so ``r.json()`` threw and the health state stayed null
("API offline") for every visitor of sarofrontend.fly.dev, including demo
attendees (demo readiness review 2026-07-19, finding F2). The Vite dev proxy had
the same gap, so local dev showed the same false badge.

Config files can't be executed in CI, so this pins both proxies textually:
nginx must route /health to the backend before the SPA fallback can swallow it,
and the dev proxy must list /health alongside /api.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = ROOT / "frontend" / "nginx.conf"
VITE_CONFIG = ROOT / "frontend" / "vite.config.js"

pytestmark = [pytest.mark.regression, pytest.mark.unit]


def test_nginx_proxies_health_to_backend():
    conf = NGINX_CONF.read_text(encoding="utf-8")
    m = re.search(r"location\s*=?\s*/health\s*\{([^}]*)\}", conf)
    assert m, (
        "frontend/nginx.conf must define a location for /health — without it the "
        "SPA fallback serves index.html and Sidebar.jsx renders 'API offline'"
    )
    assert re.search(r"proxy_pass\s+https://saro-backend\.fly\.dev/health", m.group(1)), (
        "/health location must proxy_pass to the canonical backend health endpoint "
        "(docs/ARCHITECTURE.md: GET /health on saro-backend.fly.dev)"
    )


def test_vite_dev_proxy_covers_health():
    conf = VITE_CONFIG.read_text(encoding="utf-8")
    assert re.search(r"[\"']/health[\"']\s*:", conf), (
        "vite.config.js dev proxy must map /health to the local backend so the "
        "sidebar health badge works in dev exactly as in production"
    )


def test_health_payload_carries_db_ok_boolean():
    """Sidebar.jsx renders `DB ${health.db_ok ? "ok" : "error"}`, and CLAUDE.md /
    docs/ARCHITECTURE.md document db_ok in the /health contract — but the payload
    only carried `database: "ok"`, so the badge said "DB error" even when healthy."""
    from fastapi.testclient import TestClient

    from main import app

    # No `with` — the lifespan runs Postgres-only migrations that can't execute
    # on the suite's SQLite; /health itself needs no startup hooks.
    body = TestClient(app).get("/health").json()
    assert isinstance(body.get("db_ok"), bool), (
        f"/health must include a boolean db_ok field (got: {sorted(body.keys())})"
    )
    assert body["db_ok"] == (body.get("database") == "ok")
