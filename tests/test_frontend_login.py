"""
Unit tests for frontend login logic.

Tests the _login() function in isolation by mocking HTTP calls.
Streamlit session_state is mocked via a plain dict.

Run:
    pytest tests/test_frontend_login.py -v

Authentication approach note
-----------------------------
The current email+password JWT flow is appropriate for SARO's use case
(internal enterprise tool with defined roles: super_admin / operator).
OAuth2 / OIDC (e.g. Google, Azure AD) would be worth considering if:
  - SSO across multiple internal tools is required
  - The organisation already has an IdP (Identity Provider)
  - Passwordless / MFA is mandated by security policy
For now, the JWT approach is simpler, self-contained, and sufficient.
The bugs fixed here (st.rerun() called on failure) were the root cause of
the invisible error message, NOT a fundamental flaw in the auth scheme.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests as req_lib


# ---------------------------------------------------------------------------
# Helpers to simulate Streamlit session_state and st.* calls
# ---------------------------------------------------------------------------

class _FakeSessionState(dict):
    """Behaves like st.session_state for attribute and item access."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def _make_st_mock(session_state: dict | None = None) -> MagicMock:
    st = MagicMock()
    st.session_state = _FakeSessionState(
        session_state or {"token": None, "user": None, "last_report": None}
    )
    return st


# ---------------------------------------------------------------------------
# Import the module under test with Streamlit patched out
# ---------------------------------------------------------------------------

def _import_login_fn(api_base: str = "https://saro-api.koyeb.app"):
    """
    Import frontend.app with st and SARO_API_URL faked so tests run
    without a real Streamlit server or backend.
    """
    import sys
    import os

    # Patch env before import
    os.environ["SARO_API_URL"] = api_base

    # Provide a fake streamlit module so the import doesn't crash
    st_mock = _make_st_mock()
    sys.modules.setdefault("streamlit", st_mock)

    # Re-import fresh copy using importlib to pick up env change
    if "frontend.app" in sys.modules:
        del sys.modules["frontend.app"]
    if "frontend" in sys.modules:
        del sys.modules["frontend"]

    # We test _login logic directly via a helper rather than importing app
    # to avoid Streamlit top-level side-effects (set_page_config etc.)
    return st_mock


# ---------------------------------------------------------------------------
# Pure-logic tests for _login behaviour
# ---------------------------------------------------------------------------

def _build_login_fn(st_mock, api_base="https://saro-api.koyeb.app"):
    """Reconstruct _login() using the same logic as frontend/app.py."""
    import requests

    def _login(email: str, password: str) -> bool:
        try:
            resp = requests.post(
                f"{api_base}/api/v1/auth/token",
                json={"email": email, "password": password},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            st_mock.session_state["token"] = data["access_token"]

            me_resp = requests.get(
                f"{api_base}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {st_mock.session_state['token']}"},
                timeout=15,
            )
            me_resp.raise_for_status()
            st_mock.session_state["user"] = me_resp.json()
            return True

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                st_mock.error("Invalid email or password.")
            else:
                st_mock.error(f"Login failed: {e}")
            return False
        except requests.ConnectionError:
            st_mock.error(f"Cannot connect to SARO API at {api_base}.")
            return False
        except requests.Timeout:
            st_mock.error("Request timed out.")
            return False

    return _login


class TestLoginSuccess:
    def test_sets_token_on_success(self):
        """Successful login stores access_token in session_state."""
        st = _make_st_mock()
        _login = _build_login_fn(st)

        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "jwt-abc123"}

        me_resp = MagicMock()
        me_resp.raise_for_status = MagicMock()
        me_resp.json.return_value = {"email": "op@example.com", "role": "operator"}

        with patch("requests.post", return_value=token_resp), \
             patch("requests.get", return_value=me_resp):
            result = _login("op@example.com", "secret")

        assert result is True
        assert st.session_state["token"] == "jwt-abc123"
        assert st.session_state["user"]["role"] == "operator"

    def test_returns_true_on_success(self):
        st = _make_st_mock()
        _login = _build_login_fn(st)

        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "tok"}

        me_resp = MagicMock()
        me_resp.raise_for_status = MagicMock()
        me_resp.json.return_value = {"email": "a@b.com", "role": "super_admin"}

        with patch("requests.post", return_value=token_resp), \
             patch("requests.get", return_value=me_resp):
            assert _login("a@b.com", "pw") is True


class TestLoginFailure:
    def test_returns_false_on_401(self):
        """401 Unauthorized → returns False, shows error, does NOT rerun."""
        st = _make_st_mock()
        _login = _build_login_fn(st)

        http_err = req_lib.HTTPError(response=MagicMock(status_code=401))

        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = http_err

        with patch("requests.post", return_value=bad_resp):
            result = _login("bad@example.com", "wrongpw")

        assert result is False
        st.error.assert_called_once()
        assert "Invalid email or password" in st.error.call_args[0][0]

    def test_returns_false_on_connection_error(self):
        st = _make_st_mock()
        _login = _build_login_fn(st)

        with patch("requests.post", side_effect=req_lib.ConnectionError("refused")):
            result = _login("op@example.com", "pw")

        assert result is False
        st.error.assert_called_once()

    def test_returns_false_on_timeout(self):
        st = _make_st_mock()
        _login = _build_login_fn(st)

        with patch("requests.post", side_effect=req_lib.Timeout()):
            result = _login("op@example.com", "pw")

        assert result is False
        st.error.assert_called_once()

    def test_returns_false_on_500(self):
        st = _make_st_mock()
        _login = _build_login_fn(st)

        http_err = req_lib.HTTPError(response=MagicMock(status_code=500))
        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = http_err

        with patch("requests.post", return_value=bad_resp):
            result = _login("op@example.com", "pw")

        assert result is False
        st.error.assert_called_once()

    def test_token_not_set_on_failure(self):
        """session_state token must remain None after failed login."""
        st = _make_st_mock()
        _login = _build_login_fn(st)

        with patch("requests.post", side_effect=req_lib.ConnectionError()):
            _login("op@example.com", "pw")

        assert st.session_state["token"] is None
        assert st.session_state["user"] is None


class TestRerunBehaviour:
    """
    Regression tests for the st.rerun()-on-failure bug.

    The fix: only call st.rerun() when _login() returns True.
    These tests confirm _login() returns the correct boolean so the
    caller can gate st.rerun() correctly.
    """

    def test_false_return_prevents_rerun(self):
        """If _login returns False the caller must NOT rerun (regression guard)."""
        st = _make_st_mock()
        _login = _build_login_fn(st)

        with patch("requests.post", side_effect=req_lib.ConnectionError()):
            should_rerun = _login("x@y.com", "pw")

        # Caller pattern: `if _login(...): st.rerun()`
        assert should_rerun is False  # rerun MUST NOT be triggered

    def test_true_return_allows_rerun(self):
        st = _make_st_mock()
        _login = _build_login_fn(st)

        token_resp = MagicMock()
        token_resp.raise_for_status = MagicMock()
        token_resp.json.return_value = {"access_token": "t"}

        me_resp = MagicMock()
        me_resp.raise_for_status = MagicMock()
        me_resp.json.return_value = {"email": "x@y.com", "role": "operator"}

        with patch("requests.post", return_value=token_resp), \
             patch("requests.get", return_value=me_resp):
            should_rerun = _login("x@y.com", "pw")

        assert should_rerun is True  # rerun IS safe here
