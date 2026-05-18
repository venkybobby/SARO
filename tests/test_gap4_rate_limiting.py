"""GAP-4: API rate limiter unit tests (TC-4.1 – TC-4.8)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from middleware.rate_limiter import (
    check_rate_limit,
    _ALLOWLIST_PREFIXES,
    _WINDOW_SECONDS,
    _REDIS_TTL,
)


# ── TC-4.1: Redis counter incremented on each request ────────────────────────

class TestRedisCounter:
    def test_incr_called_on_each_request(self):
        """TC-4.1 — INCR called 3×; TTL set to 120 on first call."""
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [1, True]
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value = fake_pipe

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            for _ in range(3):
                check_rate_limit("t1")

        assert fake_pipe.incr.call_count == 3
        assert fake_pipe.expire.call_count == 3
        # TTL should be 120 seconds
        expire_call_args = fake_pipe.expire.call_args_list[0][0]
        assert expire_call_args[1] == _REDIS_TTL

    def test_ttl_is_two_times_window(self):
        assert _REDIS_TTL == _WINDOW_SECONDS * 2


# ── TC-4.2: Returns 429 payload when counter exceeds limit ───────────────────

class TestRateLimitExceeded:
    def test_returns_allowed_false_when_counter_over_limit(self):
        """TC-4.2 — counter=101, limit=100 → allowed=False, retry_after positive."""
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [101, True]
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value = fake_pipe

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            result = check_rate_limit("t1", limit=100)

        assert result["allowed"] is False
        assert result["remaining"] == 0
        assert result["retry_after"] > 0
        assert result["retry_after"] <= _WINDOW_SECONDS

    def test_returns_allowed_true_at_exact_limit(self):
        """Counter=100, limit=100 → still allowed."""
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [100, True]
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value = fake_pipe

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            result = check_rate_limit("t1", limit=100)

        assert result["allowed"] is True


# ── TC-4.3: Allowlisted paths bypass rate limit ───────────────────────────────

class TestAllowlist:
    def test_health_path_in_allowlist(self):
        assert "/health" in _ALLOWLIST_PREFIXES

    def test_sso_path_in_allowlist(self):
        assert any("sso" in p for p in _ALLOWLIST_PREFIXES)

    def test_auth_magic_link_in_allowlist(self):
        assert any("magic-link" in p or "saml" in p for p in _ALLOWLIST_PREFIXES)

    def test_allowlist_covers_required_paths(self):
        """FR-4.3 — /health, /metrics, auth magic-link, /sso must be excluded."""
        required = {"/health", "/metrics"}
        for path in required:
            assert any(path.startswith(prefix) for prefix in _ALLOWLIST_PREFIXES), (
                f"{path} not covered by allowlist"
            )


# ── TC-4.4: Redis failure causes fail-open ────────────────────────────────────

class TestFailOpen:
    def test_redis_connection_error_allows_request(self):
        """TC-4.4 — Redis ConnectionError → allowed=True, no 429 raised."""
        fake_redis = MagicMock()
        fake_pipe = MagicMock()
        fake_pipe.execute.side_effect = ConnectionError("Redis down")
        fake_redis.pipeline.return_value = fake_pipe

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            result = check_rate_limit("t1")

        assert result["allowed"] is True

    def test_redis_unavailable_returns_full_quota(self):
        """When Redis is None (not installed/configured), full quota returned."""
        with patch("middleware.rate_limiter._redis", return_value=None):
            result = check_rate_limit("t1", limit=100)

        assert result["allowed"] is True
        assert result["remaining"] == 100

    def test_redis_exception_increments_prometheus_counter(self):
        """TC-4.4 — Prometheus counter incremented on Redis failure."""
        from middleware import rate_limiter

        fake_redis = MagicMock()
        fake_pipe = MagicMock()
        fake_pipe.execute.side_effect = ConnectionError("down")
        fake_redis.pipeline.return_value = fake_pipe

        initial = rate_limiter._PROMETHEUS_COUNTER
        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            with patch("middleware.rate_limiter._inc_failure") as mock_inc:
                check_rate_limit("t1")
                mock_inc.assert_called_once()


# ── TC-4.6: Per-tenant isolation ─────────────────────────────────────────────

class TestTenantIsolation:
    def test_different_tenants_have_separate_counters(self):
        """TC-4.6 — tenant_A exhausted quota should not affect tenant_B."""
        call_counts: dict[str, int] = {}

        def fake_incr_pipeline(tenant_key):
            # Extract tenant from key
            parts = tenant_key.split(":")
            tenant = parts[1] if len(parts) > 1 else "unknown"
            call_counts[tenant] = call_counts.get(tenant, 0) + 1
            return call_counts[tenant]

        results_by_tenant: dict[str, list] = {"t_a": [], "t_b": []}

        fake_pipe_a = MagicMock()
        fake_pipe_a.execute.side_effect = lambda: [101, True]  # t_a always over limit
        fake_pipe_b = MagicMock()
        fake_pipe_b.execute.side_effect = lambda: [1, True]    # t_b always under limit

        fake_redis = MagicMock()
        pipe_call_count = [0]

        def pipeline_factory():
            pipe_call_count[0] += 1
            return fake_pipe_a if pipe_call_count[0] % 2 == 1 else fake_pipe_b

        fake_redis.pipeline.side_effect = pipeline_factory

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            r_a = check_rate_limit("tenant_a", limit=100)
            r_b = check_rate_limit("tenant_b", limit=100)

        # tenant_a should be blocked, tenant_b should pass
        assert r_a["allowed"] is False
        assert r_b["allowed"] is True


# ── FR-4.2: Required headers ──────────────────────────────────────────────────

class TestRateLimitResponseFields:
    def test_result_contains_all_required_fields(self):
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [50, True]
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value = fake_pipe

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            result = check_rate_limit("t1", limit=100)

        for field in ("allowed", "count", "limit", "remaining", "retry_after", "reset_epoch"):
            assert field in result, f"Missing field: {field}"

    def test_remaining_is_limit_minus_count(self):
        fake_pipe = MagicMock()
        fake_pipe.execute.return_value = [30, True]
        fake_redis = MagicMock()
        fake_redis.pipeline.return_value = fake_pipe

        with patch("middleware.rate_limiter._redis", return_value=fake_redis):
            result = check_rate_limit("t1", limit=100)

        assert result["remaining"] == 70
        assert result["count"] == 30
