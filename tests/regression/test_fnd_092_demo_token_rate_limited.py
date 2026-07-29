"""FND-092: `GET /api/v1/demo/token` (routers/demo.py) was missing from
`middleware/rate_limiter.py`'s `_AUTH_STRICT_PREFIXES`, so it fell through to
the unthrottled default branch instead of the strict 10/min/IP cap sibling
token-minting endpoints get (`/auth/token`, `/auth/login`, `/auth/magic-link`).
Flagged by security-auditor during the FND-088 review as a pre-existing,
non-blocking gap worth closing on its own.

Originally logged as FND-090; renumbered to FND-092 after main independently
landed an unrelated FND-090/FND-091 pair (tenants.settings_json migration gap
+ its database.py self-heal follow-up) while this fix was in review.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from middleware import rate_limiter
from middleware.rate_limiter import RateLimiterMiddleware, _AUTH_RATE_LIMIT_RPM

pytestmark = [pytest.mark.regression, pytest.mark.unit]


def test_demo_token_is_in_auth_strict_prefixes():
    assert "/api/v1/demo/token" in rate_limiter._AUTH_STRICT_PREFIXES


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimiterMiddleware)

    @app.get("/api/v1/demo/token")
    def demo_token():
        return {"ok": True}

    return app


def test_demo_token_gets_the_strict_auth_per_ip_limit():
    calls: list[tuple[str, int]] = []

    def _fake(key, limit):
        calls.append((key, limit))
        return {
            "allowed": True,
            "count": 1,
            "limit": limit,
            "remaining": limit,
            "retry_after": 1,
            "reset_epoch": 0,
        }

    with patch.object(rate_limiter, "check_rate_limit", side_effect=_fake):
        client = TestClient(_app())
        client.get("/api/v1/demo/token")

    assert len(calls) == 1, (
        f"expected demo/token to hit the limiter exactly once: {calls}"
    )
    key, limit = calls[0]
    assert key.startswith("auth-ip:")
    assert limit == _AUTH_RATE_LIMIT_RPM


def test_demo_token_blocked_returns_429():
    def _fake(key, limit):
        return {
            "allowed": False,
            "count": limit + 1,
            "limit": limit,
            "remaining": 0,
            "retry_after": 30,
            "reset_epoch": 0,
        }

    with patch.object(rate_limiter, "check_rate_limit", side_effect=_fake):
        client = TestClient(_app())
        resp = client.get("/api/v1/demo/token")

    assert resp.status_code == 429
    assert resp.json()["error"] == "rate_limit_exceeded"
