"""Auth hardening: the rate limiter actually enforces, and auth endpoints get a
stricter per-IP limit.

Regression for two issues:
1. "/" sat in the prefix allowlist, so path.startswith("/") matched EVERY request
   and the limiter was a global no-op.
2. Login / magic-link endpoints were fully exempt — no brute-force / enumeration cap.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from middleware import rate_limiter
from middleware.rate_limiter import (
    RateLimiterMiddleware,
    _AUTH_RATE_LIMIT_RPM,
    _EXACT_ALLOWLIST,
    _RATE_LIMIT_RPM,
)

pytestmark = [pytest.mark.regression, pytest.mark.unit]


def test_root_is_exact_not_prefix_allowlisted():
    assert "/" in _EXACT_ALLOWLIST
    # "/" must NOT live in the startswith() prefix tuple (that was the no-op bug).
    assert "/" not in rate_limiter._ALLOWLIST_PREFIXES


def test_auth_limit_is_stricter_than_global():
    assert _AUTH_RATE_LIMIT_RPM < _RATE_LIMIT_RPM


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimiterMiddleware)

    @app.get("/api/v1/scan")
    def scan():
        return {"ok": True}

    @app.post("/api/v1/auth/token")
    def token():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def test_only_auth_endpoints_are_throttled():
    """Auth-only scope: /health (allowlisted) and /api/v1/scan (non-auth) bypass
    the limiter entirely; only the auth endpoint is throttled, keyed per-IP."""
    calls: list[tuple[str, int]] = []

    def _fake(key, limit):
        calls.append((key, limit))
        return {"allowed": True, "count": 1, "limit": limit,
                "remaining": limit, "retry_after": 1, "reset_epoch": 0}

    with patch.object(rate_limiter, "check_rate_limit", side_effect=_fake):
        client = TestClient(_app())
        client.get("/health")              # allowlisted → no limiter call
        client.get("/api/v1/scan")         # non-auth → bypass (preserves prior behavior)
        client.post("/api/v1/auth/token")  # strict per-IP limit

    # Exactly one limiter call — the auth endpoint — keyed per-IP at the strict limit.
    assert len(calls) == 1
    key, limit = calls[0]
    assert key.startswith("auth-ip:")
    assert limit == _AUTH_RATE_LIMIT_RPM
    assert _AUTH_RATE_LIMIT_RPM < _RATE_LIMIT_RPM


def test_blocked_request_returns_429():
    def _fake(key, limit):
        return {"allowed": False, "count": limit + 1, "limit": limit,
                "remaining": 0, "retry_after": 30, "reset_epoch": 0}

    with patch.object(rate_limiter, "check_rate_limit", side_effect=_fake):
        client = TestClient(_app())
        resp = client.post("/api/v1/auth/token")

    assert resp.status_code == 429
    assert resp.json()["error"] == "rate_limit_exceeded"
