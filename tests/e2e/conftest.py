"""Fixtures for the live demo E2E suite (RB-006 automation).

These tests hit the DEPLOYED apps (Fly.io by default) — they are a pre-demo
gate (RB-006 T-24h / T-1h), not a hermetic CI test. They only run when
explicitly armed:

    SARO_LIVE_E2E=1 pytest tests/e2e -m e2e -q

Base URLs are overridable so the same gate can point at local dev or staging:

    SARO_E2E_BACKEND=http://localhost:8000 \
    SARO_E2E_FRONTEND=http://localhost:5173 \
    SARO_LIVE_E2E=1 pytest tests/e2e -m e2e
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

BACKEND = os.environ.get("SARO_E2E_BACKEND", "https://saro-backend.fly.dev").rstrip("/")
FRONTEND = os.environ.get("SARO_E2E_FRONTEND", "https://sarofrontend.fly.dev").rstrip(
    "/"
)

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "demo-e2e"


@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return FRONTEND


@pytest.fixture(scope="session")
def api() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BACKEND, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def demo_token(api: httpx.Client) -> str:
    """RB-006 §A: the single most demo-critical check — mint the public demo JWT."""
    r = api.get("/api/v1/demo/token")
    assert r.status_code == 200, (
        f"GET /api/v1/demo/token returned {r.status_code} — RB-006 §A: if 503, "
        "SARO_DEMO_TENANT_ID is unset on the deployed backend "
        "(run scripts/seed_demo_tenant.py, set the secret, redeploy)."
    )
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(demo_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {demo_token}"}


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_DIR
