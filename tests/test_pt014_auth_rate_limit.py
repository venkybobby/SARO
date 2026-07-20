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


def test_only_auth_and_evaluate_endpoints_are_throttled():
    """Scoped throttling: auth endpoints (strict, brute-force defence) and
    evaluate/ingest endpoints (compute-heavy, STORY-365) are limited per-IP.
    Everything else — including allowlisted infra paths — bypasses the limiter;
    global per-tenant limiting remains a separate, load-reviewed change."""
    calls: list[tuple[str, int]] = []

    def _fake(key, limit):
        calls.append((key, limit))
        return {"allowed": True, "count": 1, "limit": limit,
                "remaining": limit, "retry_after": 1, "reset_epoch": 0}

    with patch.object(rate_limiter, "check_rate_limit", side_effect=_fake):
        client = TestClient(_app())
        client.get("/health")               # allowlisted → no limiter call
        client.get("/api/v1/dashboard")     # ordinary read → bypass
        client.post("/api/v1/auth/token")   # strict per-IP auth limit
        client.get("/api/v1/scan")          # evaluate path → per-IP evaluate limit

    assert len(calls) == 2, f"unexpected limiter scope: {calls}"

    auth_key, auth_limit = calls[0]
    assert auth_key.startswith("auth-ip:")
    assert auth_limit == _AUTH_RATE_LIMIT_RPM
    assert _AUTH_RATE_LIMIT_RPM < _RATE_LIMIT_RPM

    eval_key, eval_limit = calls[1]
    assert eval_key.startswith("eval-ip:")
    assert eval_limit == rate_limiter._EVALUATE_RATE_LIMIT_RPM
    # Evaluate is heavier than a login but must stay below the global ceiling.
    assert _AUTH_RATE_LIMIT_RPM < eval_limit <= _RATE_LIMIT_RPM


def test_blocked_request_returns_429():
    def _fake(key, limit):
        return {"allowed": False, "count": limit + 1, "limit": limit,
                "remaining": 0, "retry_after": 30, "reset_epoch": 0}

    with patch.object(rate_limiter, "check_rate_limit", side_effect=_fake):
        client = TestClient(_app())
        resp = client.post("/api/v1/auth/token")

    assert resp.status_code == 429
    assert resp.json()["error"] == "rate_limit_exceeded"
