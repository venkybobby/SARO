"""
S-000: Demo Tenant Seed Script — unit tests.

Tests that:
  1. get_or_create_demo_tenant is idempotent (returns existing tenant on 2nd call).
  2. ingest_seed_payloads builds correct request payloads.
  3. write_env_demo writes expected keys to .env file.
  4. verify_dashboard parses both response shapes (total_audits / audit_count).
  5. SEED_PAYLOADS covers all four required verticals.
  6. resolve_demo_credentials() returns a valid email + a strong password,
     generated (not hardcoded) unless overridden via env vars.
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
        from scripts.seed_demo_tenant import DEMO_USER_EMAIL_DEFAULT, DEMO_TENANT_SLUG
        assert "@" in DEMO_USER_EMAIL_DEFAULT
        assert DEMO_TENANT_SLUG == "saro-demo"

    def test_resolve_demo_credentials_generates_strong_password_by_default(self):
        from scripts.seed_demo_tenant import resolve_demo_credentials
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEMO_USER_EMAIL", None)
            os.environ.pop("DEMO_USER_PASSWORD", None)
            # Isolated, definitely-nonexistent path — must not pick up a real
            # repo-root .env.demo left over from an actual run.
            email, password = resolve_demo_credentials(env_demo_path="/nonexistent/.env.demo")
        assert "@" in email
        assert len(password) >= 16

    def test_resolve_demo_credentials_honours_env_overrides(self):
        from scripts.seed_demo_tenant import resolve_demo_credentials
        with patch.dict(os.environ, {"DEMO_USER_EMAIL": "custom@example.com", "DEMO_USER_PASSWORD": "custom-pw"}):
            email, password = resolve_demo_credentials(env_demo_path="/nonexistent/.env.demo")
        assert email == "custom@example.com"
        assert password == "custom-pw"

    def test_no_hardcoded_password_literal_in_source(self):
        """Regression guard: this file is committed to a public repo."""
        src_path = os.path.join(_REPO_ROOT, "scripts", "seed_demo_tenant.py")
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        assert "SaroDemo2026!" not in content


class TestResolveDemoCredentialsPersistence:
    """Reruns without an explicit DEMO_USER_PASSWORD must not silently rotate
    a password someone is relying on — resolve_demo_credentials() should reuse
    whatever a prior run wrote to .env.demo."""

    def test_reuses_password_from_prior_env_demo(self, tmp_path):
        from scripts.seed_demo_tenant import resolve_demo_credentials
        env_demo = tmp_path / ".env.demo"
        env_demo.write_text(
            "SARO_DEMO_TENANT_ID=t-1\nDEMO_USER_EMAIL=demo@saro-demo.io\n"
            "DEMO_USER_PASSWORD=prior-run-password\n"
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEMO_USER_PASSWORD", None)
            email, password = resolve_demo_credentials(env_demo_path=str(env_demo))
        assert password == "prior-run-password"

    def test_explicit_env_var_overrides_prior_env_demo(self, tmp_path):
        from scripts.seed_demo_tenant import resolve_demo_credentials
        env_demo = tmp_path / ".env.demo"
        env_demo.write_text("DEMO_USER_PASSWORD=prior-run-password\n")
        with patch.dict(os.environ, {"DEMO_USER_PASSWORD": "forced-override"}):
            _, password = resolve_demo_credentials(env_demo_path=str(env_demo))
        assert password == "forced-override"

    def test_generates_fresh_when_no_prior_file(self, tmp_path):
        from scripts.seed_demo_tenant import resolve_demo_credentials
        env_demo = tmp_path / "does-not-exist" / ".env.demo"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEMO_USER_PASSWORD", None)
            _, password = resolve_demo_credentials(env_demo_path=str(env_demo))
        assert len(password) >= 16


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


class TestEnsureDemoUser:
    def _make_session(self, existing_id: uuid.UUID | None = None):
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, i: existing_id  # type: ignore[misc]
        session.execute.return_value.fetchone.return_value = row if existing_id else None
        return session

    @staticmethod
    def _sql_calls(session, keyword: str):
        # TextClause has no useful __repr__, so match against the raw SQL
        # string SQLAlchemy's text() stores on `.text`.
        return [
            c for c in session.execute.call_args_list
            if keyword in getattr(c.args[0], "text", "")
        ]

    def test_creates_user_when_absent(self):
        from scripts.seed_demo_tenant import ensure_demo_user
        session = self._make_session(existing_id=None)
        result = ensure_demo_user(session, str(uuid.uuid4()), "demo@saro-demo.io", "s3cret-pw")
        assert result["created"] is True
        insert_calls = self._sql_calls(session, "INSERT INTO users")
        assert len(insert_calls) == 1
        # Hashed with the backend's own argon2id hasher, not stored in plaintext
        params = insert_calls[0].args[1]
        assert params["pw"].startswith("$argon2id$")
        session.commit.assert_called_once()

    def test_resets_password_when_present(self):
        from scripts.seed_demo_tenant import ensure_demo_user
        uid = uuid.uuid4()
        session = self._make_session(existing_id=uid)
        result = ensure_demo_user(session, str(uuid.uuid4()), "demo@saro-demo.io", "new-pw")
        assert result["created"] is False
        assert result["user_id"] == str(uid)
        update_calls = self._sql_calls(session, "UPDATE users")
        assert len(update_calls) == 1
        session.commit.assert_called_once()


class TestGetDemoJwt:
    def test_sends_json_email_password_body(self):
        from scripts.seed_demo_tenant import get_demo_jwt

        resp = MagicMock()
        resp.json.return_value = {"access_token": "tok-123"}

        with patch("scripts.seed_demo_tenant.requests.post", return_value=resp) as mock_post:
            token = get_demo_jwt("https://test.local", "demo@saro-demo.io", "pw")

        assert token == "tok-123"
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"email": "demo@saro-demo.io", "password": "pw"}
        assert "data" not in kwargs


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
        # No demo_email/demo_password passed — nothing credential-shaped written
        assert "DEMO_USER_EMAIL" not in written
        assert "DEMO_USER_PASSWORD" not in written

    def test_persists_credentials_when_given(self):
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
            write_env_demo("tenant-123", "jwt-token", "https://example.com", "demo@saro-demo.io", "s3cret")

        assert "DEMO_USER_EMAIL=demo@saro-demo.io" in written
        assert "DEMO_USER_PASSWORD=s3cret" in written


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
        resp.json.return_value = {"audit_count": 850}

        with patch("scripts.seed_demo_tenant.requests.get", return_value=resp):
            assert verify_dashboard("https://test.local", "tok") is True

    def test_zero_returns_false(self):
        from scripts.seed_demo_tenant import verify_dashboard

        resp = MagicMock()
        resp.json.return_value = {"total_audits": 0}

        with patch("scripts.seed_demo_tenant.requests.get", return_value=resp):
            assert verify_dashboard("https://test.local", "tok") is False

    def test_partial_seed_returns_false(self):
        from scripts.seed_demo_tenant import verify_dashboard

        resp = MagicMock()
        resp.json.return_value = {"total_audits": 9}

        with patch("scripts.seed_demo_tenant.requests.get", return_value=resp):
            assert verify_dashboard("https://test.local", "tok") is False
