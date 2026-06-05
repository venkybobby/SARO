"""
S-000: Demo Tenant Seed Script — unit tests.

Tests that:
  1. get_or_create_demo_tenant is idempotent (returns existing tenant on 2nd call).
  2. ingest_seed_payloads builds correct request payloads.
  3. write_env_demo writes expected keys to .env file.
  4. verify_dashboard parses both response shapes (total_audits / audit_count).
  5. SEED_PAYLOADS covers all four required verticals.
  6. DEMO_USER_EMAIL / DEMO_USER_PW constants are present.
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock, patch, mock_open

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestSeedConstants:
    def test_verticals_covered(self):
        from scripts.seed_demo_tenant import SEED_PAYLOADS
        assert set(SEED_PAYLOADS.keys()) == {"finance", "healthcare", "technology", "government"}

    def test_each_vertical_has_payloads(self):
        from scripts.seed_demo_tenant import SEED_PAYLOADS
        for vertical, payloads in SEED_PAYLOADS.items():
            assert len(payloads) >= 1, f"{vertical} has no seed payloads"
            for p in payloads:
                assert "prompt" in p and "output" in p

    def test_credentials_present(self):
        from scripts.seed_demo_tenant import DEMO_USER_EMAIL, DEMO_USER_PW, DEMO_TENANT_SLUG
        assert "@" in DEMO_USER_EMAIL
        assert len(DEMO_USER_PW) >= 8
        assert DEMO_TENANT_SLUG == "saro-demo"


class TestGetOrCreateDemoTenant:
    def _make_session(self, existing_id: uuid.UUID | None = None):
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, i: existing_id  # type: ignore[misc]
        if existing_id:
            session.execute.return_value.fetchone.return_value = row
        else:
            session.execute.return_value.fetchone.return_value = None
        return session

    def test_returns_existing_tenant(self):
        from scripts.seed_demo_tenant import get_or_create_demo_tenant
        tid = uuid.uuid4()
        session = self._make_session(existing_id=tid)
        result = get_or_create_demo_tenant(session)
        assert result["tenant_id"] == str(tid)
        assert result["created"] is False
        # Should NOT attempt an INSERT when tenant already exists
        insert_calls = [
            c for c in session.execute.call_args_list
            if "INSERT INTO tenants" in str(c)
        ]
        assert len(insert_calls) == 0

    def test_creates_new_tenant(self):
        from scripts.seed_demo_tenant import get_or_create_demo_tenant
        session = self._make_session(existing_id=None)
        result = get_or_create_demo_tenant(session)
        assert result["created"] is True
        assert uuid.UUID(result["tenant_id"])  # valid UUID
        session.commit.assert_called_once()


class TestIngestSeedPayloads:
    def test_posts_correct_fields(self):
        from scripts.seed_demo_tenant import ingest_seed_payloads, SEED_PAYLOADS

        posted: list[dict] = []

        def fake_post(url: str, json: dict, headers: dict, timeout: int):
            posted.append(json)
            resp = MagicMock()
            resp.status_code = 201
            resp.json.return_value = {"audit_id": str(uuid.uuid4())}
            return resp

        with patch("scripts.seed_demo_tenant.requests.post", side_effect=fake_post):
            results = ingest_seed_payloads("https://test.local", "tok", "tenant-1")

        total_payloads = sum(len(v) for v in SEED_PAYLOADS.values())
        assert results["success"] == total_payloads
        assert results["failed"] == 0
        assert len(results["audit_ids"]) == total_payloads

        # Verify shape of first request
        assert "prompt" in posted[0]
        assert "raw_output" in posted[0]
        assert "vertical" in posted[0]
        assert posted[0]["source_model"] == "internal"

    def test_counts_failures(self):
        from scripts.seed_demo_tenant import ingest_seed_payloads

        def fake_post(url: str, json: dict, headers: dict, timeout: int):
            resp = MagicMock()
            resp.status_code = 500
            resp.text = "Internal Server Error"
            return resp

        with patch("scripts.seed_demo_tenant.requests.post", side_effect=fake_post):
            results = ingest_seed_payloads("https://test.local", "tok", "tenant-1")

        assert results["success"] == 0
        assert results["failed"] > 0


class TestWriteEnvDemo:
    def test_writes_expected_keys(self):
        from scripts.seed_demo_tenant import write_env_demo

        written = ""

        def fake_open(path, mode="r"):
            nonlocal written
            m = mock_open()()
            def write(s: str) -> None:
                nonlocal written
                written += s
            m.write = write
            m.__enter__ = lambda s: m
            m.__exit__ = MagicMock(return_value=False)
            return m

        with patch("builtins.open", side_effect=fake_open):
            write_env_demo("tenant-123", "jwt-token", "https://example.com")

        assert "SARO_DEMO_TENANT_ID=tenant-123" in written
        assert "SARO_DEMO_TOKEN=jwt-token" in written
        assert "SARO_DEMO_URL=https://example.com" in written


class TestVerifyDashboard:
    def test_total_audits_key(self):
        from scripts.seed_demo_tenant import verify_dashboard

        resp = MagicMock()
        resp.json.return_value = {"total_audits": 800}

        with patch("scripts.seed_demo_tenant.requests.get", return_value=resp):
            assert verify_dashboard("https://test.local", "tok") is True

    def test_audit_count_key(self):
        from scripts.seed_demo_tenant import verify_dashboard

        resp = MagicMock()
        resp.json.return_value = {"audit_count": 800}

        with patch("scripts.seed_demo_tenant.requests.get", return_value=resp):
            assert verify_dashboard("https://test.local", "tok") is True

    def test_zero_returns_false(self):
        from scripts.seed_demo_tenant import verify_dashboard

        resp = MagicMock()
        resp.json.return_value = {"total_audits": 0}

        with patch("scripts.seed_demo_tenant.requests.get", return_value=resp):
            assert verify_dashboard("https://test.local", "tok") is False
