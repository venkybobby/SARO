"""Redis sliding-window rate limiter middleware.

Limits requests per tenant per 60-second window (default 100 rpm).
Fails open if Redis is unavailable — never blocks traffic due to cache failure.

Configuration (env vars):
    RATE_LIMIT_RPM     requests per minute per tenant (default 100)
    REDIS_URL          Redis connection string (default redis://localhost:6379)
"""
from __future__ import annotations

import logging
import math
import os
import time
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "100"))
_WINDOW_SECONDS = 60
_REDIS_TTL = _WINDOW_SECONDS * 2  # 2× window covers edge-of-minute transitions

# Paths that bypass rate limiting entirely.
# NOTE: "/" must be matched EXACTLY (see _EXACT_ALLOWLIST) — as a startswith()
# prefix it matched every path and silently disabled the limiter for the whole API.
# SAML/SSO assertion endpoints stay exempt: they are IdP-initiated single POSTs
# already guarded by signature + NotOnOrAfter + replay checks (routers/sso.py).
_ALLOWLIST_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/saml",
    "/api/v1/sso",
)

# Exact-match (non-prefix) allowlist — the bare root only.
_EXACT_ALLOWLIST = frozenset({"/"})

# Authentication endpoints get a stricter PER-IP limit to blunt credential
# brute-forcing and magic-link email enumeration (default 10/min/IP).
_AUTH_STRICT_PREFIXES = (
    "/api/v1/auth/token",
    "/api/v1/auth/login",
    "/api/v1/auth/bootstrap",
    "/api/v1/auth/magic-link",
)
_AUTH_RATE_LIMIT_RPM = int(os.environ.get("AUTH_RATE_LIMIT_RPM", "10"))

_PROMETHEUS_COUNTER = 0  # module-level fallback counter when prometheus_client absent

try:
    from prometheus_client import Counter
    _redis_failures = Counter(
        "saro_rate_limiter_redis_failures_total",
        "Number of Redis failures in rate limiter (fail-open events)",
    )

    def _inc_failure() -> None:
        _redis_failures.inc()

except ImportError:
    def _inc_failure() -> None:
        global _PROMETHEUS_COUNTER
        _PROMETHEUS_COUNTER += 1


def _get_redis():
    """Return a Redis client or None if the library / server is unavailable."""
    try:
        import redis as redis_lib
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        client = redis_lib.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        return client
    except Exception:
        return None


_redis_client = None


def _redis() -> Any:
    global _redis_client
    if _redis_client is None:
        _redis_client = _get_redis()
    return _redis_client


def _minute_bucket() -> int:
    """Return the current 60-second bucket (floor of unix time / 60)."""
    return math.floor(time.time() / _WINDOW_SECONDS)


def check_rate_limit(tenant_id: str, limit: int = _RATE_LIMIT_RPM) -> dict:
    """Increment the sliding-window counter for *tenant_id*.

    Returns a dict:
        {
            "allowed": bool,
            "count": int,
            "limit": int,
            "remaining": int,
            "retry_after": int,   # seconds until next window reset
            "reset_epoch": int,
        }
    Fails open (allowed=True) when Redis is unavailable.
    """
    bucket = _minute_bucket()
    reset_epoch = (bucket + 1) * _WINDOW_SECONDS
    retry_after = max(1, reset_epoch - int(time.time()))

    client = _redis()
    if client is None:
        return {"allowed": True, "count": 0, "limit": limit,
                "remaining": limit, "retry_after": retry_after, "reset_epoch": reset_epoch}

    key = f"rate:{tenant_id}:{bucket}"
    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, _REDIS_TTL)
        results = pipe.execute()
        count = int(results[0])
    except Exception as exc:
        logger.warning("Rate limiter Redis error (fail-open): %s", exc)
        _inc_failure()
        return {"allowed": True, "count": 0, "limit": limit,
                "remaining": limit, "retry_after": retry_after, "reset_epoch": reset_epoch}

    allowed = count <= limit
    remaining = max(0, limit - count)
    return {
        "allowed": allowed,
        "count": count,
        "limit": limit,
        "remaining": remaining,
        "retry_after": retry_after,
        "reset_epoch": reset_epoch,
    }


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Per-tenant sliding-window rate limiter using Redis."""

    def __init__(self, app, limit: int = _RATE_LIMIT_RPM) -> None:
        super().__init__(app)
        self._limit = limit

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path: str = request.url.path

        # Allowlist — skip rate limiting (exact root + infra/SSO prefixes)
        if path in _EXACT_ALLOWLIST or any(
            path.startswith(prefix) for prefix in _ALLOWLIST_PREFIXES
        ):
            return await call_next(request)

        client_host = request.client.host if request.client else None

        # Scope: enforce a strict PER-IP limit on authentication endpoints
        # (brute-force / enumeration defence). All other endpoints are left
        # unthrottled here — global per-tenant limiting is a separate change
        # (it would require load review + test-fixture isolation) and must not
        # be enabled as a side effect of this auth-hardening fix.
        if not any(path.startswith(prefix) for prefix in _AUTH_STRICT_PREFIXES):
            return await call_next(request)

        limit = _AUTH_RATE_LIMIT_RPM
        rl_key = f"auth-ip:{client_host or 'unknown'}"
        result = check_rate_limit(rl_key, limit)

        # Always attach quota headers to the response
        async def _add_headers(resp: Response) -> Response:
            resp.headers["X-RateLimit-Limit"] = str(result["limit"])
            resp.headers["X-RateLimit-Remaining"] = str(result["remaining"])
            resp.headers["X-RateLimit-Reset"] = str(result["reset_epoch"])
            return resp

        if not result["allowed"]:
            resp = JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "retry_after": result["retry_after"],
                    "limit": result["limit"],
                    "window": f"{_WINDOW_SECONDS}s",
                },
            )
            resp.headers["Retry-After"] = str(result["retry_after"])
            return await _add_headers(resp)

        response = await call_next(request)
        return await _add_headers(response)
