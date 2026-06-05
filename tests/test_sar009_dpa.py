"""SAR-009: GDPR Art. 28 DPA in-app delivery — test suite (8 tests).

Tests cover:
  1. Template file presence
  2. Service module presence
  3. Markdown rendering injects tenant name
  4. 403 for ai_auditor persona
  5. 200 for compliance_lead persona
  6. AuditEvent logged on download
  7. Content-Disposition header contains filename and .pdf
  8. _DPA_VERSION constant equals "1.0"
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap sys.path so imports resolve regardless of pytest working directory
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(persona_role: str = "compliance_lead") -> MagicMock:
    from models import User

    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.tenant_id = uuid.uuid4()
    u.persona_role = persona_role
    u.role = "operator"
    u.is_active = True
    return u


def _make_mock_tenant(name: str = "Test Corp", slug: str = "test-corp") -> MagicMock:
    from models import Tenant

    t = MagicMock(spec=Tenant)
    t.id = uuid.uuid4()
    t.name = name
    t.slug = slug
    return t


def _override_db(user=None, tenant=None):
    """Return a get_db override that yields a mock session."""

    def _inner():
        mock_db = MagicMock()

        def _query(model):
            q = MagicMock()
            model_name = getattr(model, "__name__", str(model))
            if model_name == "User":
                q.filter.return_value.first.return_value = user
            elif model_name == "Tenant":
                q.filter.return_value.first.return_value = tenant
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = _query
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        yield mock_db

    return _inner


# ---------------------------------------------------------------------------
# Tests 1–2: file existence (pure filesystem, no import)
# ---------------------------------------------------------------------------


def test_dpa_template_file_exists():
    """Template file must be present at docs/legal/saro-dpa-template-v1.0.md."""
    template = _REPO_ROOT / "docs" / "legal" / "saro-dpa-template-v1.0.md"
    assert template.exists(), f"DPA template missing: {template}"


def test_dpa_service_module_exists():
    """services/dpa_service.py must exist."""
    service = _REPO_ROOT / "services" / "dpa_service.py"
    assert service.exists(), f"DPA service module missing: {service}"


# ---------------------------------------------------------------------------
# Test 3: markdown rendering
# ---------------------------------------------------------------------------


def test_render_dpa_markdown_injects_tenant_name():
    """_render_dpa_markdown must inject the tenant name into the rendered output."""
    from services.dpa_service import _render_dpa_markdown

    result = _render_dpa_markdown(tenant_name="Acme Corp")
    assert "Acme Corp" in result, "Tenant name not found in rendered DPA markdown"


# ---------------------------------------------------------------------------
# Tests 4–7: HTTP endpoint behaviour
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def _client():
    """Return a TestClient with dependency overrides reset after each test."""
    from fastapi.testclient import TestClient
    from main import app

    yield TestClient(app, raise_server_exceptions=False)
    # Reset overrides after every test
    app.dependency_overrides.clear()


def _setup_overrides(user, tenant=None):
    """Install dependency overrides for get_current_user and get_db."""
    from auth import get_current_user
    from database import get_db
    from main import app

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _override_db(user=user, tenant=tenant)


def test_dpa_endpoint_returns_403_for_ai_auditor(_client):
    """GET /api/v1/compliance/dpa must return 403 for ai_auditor persona."""
    user = _make_mock_user(persona_role="ai_auditor")
    _setup_overrides(user, tenant=_make_mock_tenant())

    resp = _client.get("/api/v1/compliance/dpa")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


def test_dpa_endpoint_returns_200_for_compliance_lead(_client):
    """GET /api/v1/compliance/dpa must return 200 for compliance_lead."""
    user = _make_mock_user(persona_role="compliance_lead")
    tenant = _make_mock_tenant()
    _setup_overrides(user, tenant=tenant)

    with patch("services.dpa_service.generate_dpa_pdf", return_value=b"%PDF-fake"):
        resp = _client.get("/api/v1/compliance/dpa")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert "SARO_DPA" in resp.headers.get("content-disposition", ""), (
        f"Expected SARO_DPA in Content-Disposition, got: {resp.headers}"
    )


def test_dpa_endpoint_logs_audit_event(_client):
    """GET /api/v1/compliance/dpa must call db.add() with a dpa_downloaded AuditEvent."""
    from database import get_db
    from main import app
    from auth import get_current_user

    user = _make_mock_user(persona_role="compliance_lead")
    tenant = _make_mock_tenant()

    # Capture the mock_db so we can inspect calls
    captured_db: list = []

    def _db_override():
        mock_db = MagicMock()

        def _query(model):
            q = MagicMock()
            model_name = getattr(model, "__name__", str(model))
            if model_name == "Tenant":
                q.filter.return_value.first.return_value = tenant
            else:
                q.filter.return_value.first.return_value = None
            return q

        mock_db.query.side_effect = _query
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        captured_db.append(mock_db)
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = _db_override

    with patch("services.dpa_service.generate_dpa_pdf", return_value=b"%PDF-fake"):
        resp = _client.get("/api/v1/compliance/dpa")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert captured_db, "DB override was never called"
    mock_db = captured_db[0]
    assert mock_db.add.called, "db.add() was not called — AuditEvent not logged"
    assert mock_db.commit.called, "db.commit() was not called"

    # Inspect the AuditEvent passed to add()
    added_obj = mock_db.add.call_args[0][0]
    assert hasattr(added_obj, "event_type"), "Added object has no event_type attribute"
    assert added_obj.event_type == "dpa_downloaded", (
        f"Expected event_type='dpa_downloaded', got '{added_obj.event_type}'"
    )


def test_dpa_pdf_has_correct_content_disposition(_client):
    """Content-Disposition header must contain 'filename' and '.pdf'."""
    user = _make_mock_user(persona_role="compliance_lead")
    tenant = _make_mock_tenant(slug="acme-corp")
    _setup_overrides(user, tenant=tenant)

    with patch("services.dpa_service.generate_dpa_pdf", return_value=b"%PDF-fake"):
        resp = _client.get("/api/v1/compliance/dpa")

    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "filename" in cd, f"Content-Disposition missing 'filename': {cd}"
    assert ".pdf" in cd, f"Content-Disposition missing '.pdf': {cd}"


# ---------------------------------------------------------------------------
# Test 8: version constant
# ---------------------------------------------------------------------------


def test_dpa_version_in_service():
    """_DPA_VERSION must equal '1.0'."""
    from services.dpa_service import _DPA_VERSION

    assert _DPA_VERSION == "1.0", f"Expected _DPA_VERSION='1.0', got '{_DPA_VERSION}'"
