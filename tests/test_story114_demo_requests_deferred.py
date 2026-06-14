"""STORY-114: demo-request intake is deferred behind a feature flag (default OFF).

The public POST /api/v1/demo/signup must fail closed (no DB write, no Slack) when
the flag is off, and behave normally when enabled. Existing data and the admin
management endpoints are untouched. The admin Demo Requests nav entry is removed.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

_ROOT = Path(__file__).parent.parent


@pytest.mark.unit
def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("DEMO_REQUESTS_ENABLED", raising=False)
    from routers.demo import _demo_requests_enabled

    assert _demo_requests_enabled() is False


@pytest.mark.unit
@pytest.mark.parametrize("val", ["true", "1", "yes", "ON"])
def test_flag_enabled_values(monkeypatch, val):
    monkeypatch.setenv("DEMO_REQUESTS_ENABLED", val)
    from routers.demo import _demo_requests_enabled

    assert _demo_requests_enabled() is True


@pytest.mark.unit
def test_signup_fails_closed_when_disabled(monkeypatch):
    monkeypatch.delenv("DEMO_REQUESTS_ENABLED", raising=False)
    from routers.demo import demo_signup

    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(demo_signup(payload=MagicMock(), background_tasks=MagicMock(), db=db))
    assert exc.value.status_code == 503
    # Fail closed: no DB access, no record created before the 503.
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_admin_demo_requests_nav_removed():
    src = (_ROOT / "frontend" / "src" / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    assert '"demo_requests"' not in src, "demo_requests must be removed from PERSONA_TABS"
    assert "demo_requests:" not in src, "demo_requests TAB_REGISTRY entry must be removed"
