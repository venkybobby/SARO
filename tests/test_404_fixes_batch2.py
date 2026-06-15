"""
Tests for the three production 404 fixes (2026-06-08 batch 2).

Endpoints under test
---------------------
GET /api/v1/aims/models           — AI model inventory
GET /api/v1/onboarding/status     — tenant onboarding checklist
GET /api/v1/governance/trust-documents — trust document catalogue
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import MagicMock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-batch2")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from auth import get_current_user  # noqa: E402
from database import get_db  # noqa: E402
from main import app  # noqa: E402
from models import AIMSDocument, User  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_TENANT_ID = uuid.uuid4()
_USER_ID = uuid.uuid4()


def _make_user(role: str = "operator") -> MagicMock:
    user = MagicMock(spec=User)
    user.id = _USER_ID
    user.tenant_id = _TENANT_ID
    user.email = "test@saro.app"
    user.role = role
    user.persona_role = "compliance_lead"
    user.is_active = True
    return user


_MOCK_USER = _make_user(role="super_admin")


def _auth_override():
    return _MOCK_USER


def _db_factory(aims_docs=None, audits=None, config=None):
    """Return a FastAPI dependency override that yields a MagicMock db session."""
    aims_docs = aims_docs or []
    audits = audits or []

    def _inner():
        mock_db = MagicMock()

        def _query(model):
            q = MagicMock()
            model_name = model.__name__ if hasattr(model, "__name__") else str(model)
            if model_name == "AIMSDocument":
                q.filter.return_value.order_by.return_value.all.return_value = aims_docs
                q.filter.return_value.first.return_value = aims_docs[0] if aims_docs else None
            elif model_name == "Audit":
                q.filter.return_value.first.return_value = audits[0] if audits else None
            elif model_name == "ClientConfig":
                q.filter.return_value.first.return_value = config
            else:
                q.filter.return_value.first.return_value = None
                q.filter.return_value.order_by.return_value.all.return_value = []
            return q

        mock_db.query.side_effect = _query
        yield mock_db

    return _inner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_no_data():
    app.dependency_overrides[get_current_user] = _auth_override
    app.dependency_overrides[get_db] = _db_factory()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_doc():
    doc = MagicMock(spec=AIMSDocument)
    doc.id = uuid.uuid4()
    doc.title = "GPT-4 Production Deployment"
    doc.version = "1.0.0"
    doc.effective_date = None
    doc.owner_email = "ai-team@corp.com"
    doc.linked_audit_ids = ["audit-1", "audit-2"]
    doc.created_at = None

    app.dependency_overrides[get_current_user] = _auth_override
    app.dependency_overrides[get_db] = _db_factory(aims_docs=[doc])
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_trust():
    """Trust-documents endpoint does NOT use get_db — only auth override needed."""
    app.dependency_overrides[get_current_user] = _auth_override
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/aims/models
# ---------------------------------------------------------------------------

class TestAimsModels:
    def test_returns_200_empty(self, client_no_data: TestClient):
        resp = client_no_data.get(f"/api/v1/aims/models?tenant_id={_TENANT_ID}")
        assert resp.status_code == 200

    def test_response_schema_keys(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/aims/models")
        assert resp.status_code == 200
        body = resp.json()
        assert "models" in body
        assert "total" in body
        assert isinstance(body["models"], list)

    def test_empty_returns_zero_total(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/aims/models")
        body = resp.json()
        assert body["total"] == 0

    def test_with_aims_doc_returns_model_entry(self, client_with_doc: TestClient):
        resp = client_with_doc.get("/api/v1/aims/models")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        model = body["models"][0]
        assert model["name"] == "GPT-4 Production Deployment"
        assert model["linked_audit_count"] == 2

    def test_tenant_id_in_response(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/aims/models")
        body = resp.json()
        assert "tenant_id" in body


# ---------------------------------------------------------------------------
# GET /api/v1/onboarding/status
# ---------------------------------------------------------------------------

class TestOnboardingStatus:
    def test_returns_200(self, client_no_data: TestClient):
        resp = client_no_data.get(f"/api/v1/onboarding/status?tenant_id={_TENANT_ID}")
        assert resp.status_code == 200

    def test_response_schema_keys(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/onboarding/status")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("tenant_id", "completed_steps", "total_steps", "completion_pct",
                    "onboarding_complete", "steps"):
            assert key in body, f"Missing key: {key}"

    def test_steps_include_expected_keys(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/onboarding/status")
        body = resp.json()
        step_keys = {s["key"] for s in body["steps"]}
        assert "first_scan" in step_keys
        assert "profile" in step_keys
        assert "aims_doc" in step_keys

    def test_completion_pct_zero_when_nothing_done(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/onboarding/status")
        body = resp.json()
        assert body["completion_pct"] == 0
        assert body["onboarding_complete"] is False

    def test_total_steps_at_least_four(self, client_no_data: TestClient):
        resp = client_no_data.get("/api/v1/onboarding/status")
        body = resp.json()
        assert body["total_steps"] >= 4


# ---------------------------------------------------------------------------
# GET /api/v1/governance/trust-documents
# ---------------------------------------------------------------------------

class TestGovernanceTrustDocuments:
    def test_returns_200(self, client_trust: TestClient):
        resp = client_trust.get("/api/v1/governance/trust-documents")
        assert resp.status_code == 200

    def test_response_schema(self, client_trust: TestClient):
        resp = client_trust.get("/api/v1/governance/trust-documents")
        body = resp.json()
        assert "documents" in body
        assert "total" in body
        assert "available_count" in body
        assert "disclaimer" in body

    def test_all_documents_returned(self, client_trust: TestClient):
        # 4 governance docs + the S-1107 tenant-isolation security evidence pack.
        resp = client_trust.get("/api/v1/governance/trust-documents")
        body = resp.json()
        assert body["total"] == 5
        keys = {d["key"] for d in body["documents"]}
        assert "security-isolation-evidence" in keys

    def test_document_keys_present(self, client_trust: TestClient):
        resp = client_trust.get("/api/v1/governance/trust-documents")
        body = resp.json()
        keys = {d["key"] for d in body["documents"]}
        assert "nist-self-assessment" in keys
        assert "eu-ai-act-position" in keys
        assert "dpa-template" in keys
        assert "soc2-roadmap" in keys

    def test_each_document_has_required_fields(self, client_trust: TestClient):
        resp = client_trust.get("/api/v1/governance/trust-documents")
        body = resp.json()
        for doc in body["documents"]:
            for field in ("key", "label", "available", "download_url"):
                assert field in doc, f"Document {doc.get('key')} missing field: {field}"

    def test_disclaimer_uses_approved_language(self, client_trust: TestClient):
        resp = client_trust.get("/api/v1/governance/trust-documents")
        body = resp.json()
        disclaimer = body["disclaimer"].lower()
        # Must NOT claim certification itself
        assert "saro certifies" not in disclaimer
        # Must NOT use forbidden "compliant"
        assert "compliant" not in disclaimer
        # Must include human review language (compliance-guard requirement)
        assert "human review" in disclaimer
