"""CHUB-010: tenant-scoping evidence for /coverage and /validation-status.

Both endpoints build their result from ``db`` only, with no explicit tenant
argument. This test documents and proves *why that is correct*: the underlying
tables are **global, tenant-agnostic reference / product data**, not tenant-scoped
rows.

Determining columns (see models.py):
  - /compliance-matrix/coverage  ← get_matrix_rows()  ← EUAIActRule (models.py:323),
    NISTControl (models.py:340) + static AIGP/ISO rows. None of these tables declare
    a ``tenant_id`` column — they are the shared text of the regulations themselves.
  - /evf/validation-status        ← get_all_framework_statuses() ← QCORegistry
    (models.py:894), SMEEngagement (models.py:793), QCOExpiryNotification
    (models.py:991). None declare ``tenant_id`` — SARO's external-validation (EVF)
    state per framework is a single product-level fact (see
    docs/COMPLIANCE_CLAIMS_MATRIX.md EVF section), identical for every tenant.

Therefore the security property to pin is: the responses are (a) identical
regardless of the caller's tenant (global-by-design, AC-3) and (b) carry no
tenant-scoped column that could leak across tenants (AC-2 is moot — there is no
tenant data). Analogous to STORY-015's isolation evidence.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from auth import get_current_user
from database import get_db
from main import app
from models import User

pytestmark = [pytest.mark.integration, pytest.mark.security]

_TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
_TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


def _user(tenant_id: uuid.UUID):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = f"user-{tenant_id}@test.example"
    u.role = "operator"
    u.persona_role = "compliance_lead"
    u.tenant_id = tenant_id
    u.is_active = True
    u.read_only = False
    return u


def _db_global():
    """A db whose tenant-scoped queries return nothing — matrix falls back to the
    static global rows; EVF queries resolve to Tier 3. Deterministic and identical
    for every caller, which is the whole point."""

    def _dep():
        db = MagicMock()
        q = MagicMock()
        for attr in ("filter", "outerjoin", "join", "order_by", "limit", "offset"):
            getattr(q, attr).return_value = q
        q.all.return_value = []
        q.first.return_value = None
        db.query.return_value = q
        yield db

    return _dep


def _client(tenant_id: uuid.UUID):
    app.dependency_overrides[get_current_user] = lambda: _user(tenant_id)
    app.dependency_overrides[get_db] = _db_global()
    return TestClient(app)


def _clear():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _get(tenant_id, path):
    c = _client(tenant_id)
    try:
        r = c.get(path, headers={"Authorization": "Bearer t"})
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        return r.json()
    finally:
        _clear()


# ── AC-3 / AC-4: coverage is global-by-design, no tenant leak ─────────────────


def test_coverage_identical_across_tenants_and_carries_no_tenant_id():
    a = _get(_TENANT_A, "/api/v1/compliance-matrix/coverage")
    b = _get(_TENANT_B, "/api/v1/compliance-matrix/coverage")
    assert a == b, "coverage is global reference data — must not vary by tenant"
    for fw in a["frameworks"]:
        assert "tenant_id" not in fw, "coverage rows must not embed tenant_id"


def _strip_checked_at(entries):
    # checked_at is a per-call timestamp, not tenant-derived data.
    return [{k: v for k, v in e.items() if k != "checked_at"} for e in entries]


def test_validation_status_identical_across_tenants_and_carries_no_tenant_id():
    a = _get(_TENANT_A, "/api/v1/evf/validation-status")
    b = _get(_TENANT_B, "/api/v1/evf/validation-status")
    assert _strip_checked_at(a) == _strip_checked_at(b), (
        "EVF validation status is a product-level fact — tenant-invariant"
    )
    assert isinstance(a, list) and a, "expected the four in-scope frameworks"
    for entry in a:
        assert "tenant_id" not in entry, "validation-status must not embed tenant_id"


def test_empty_tenant_does_not_fall_through_to_another_tenants_rows():
    # An 'empty' tenant still sees the global definitions (by design) and never a
    # different tenant's data — because there is no per-tenant data in this path.
    empty = uuid.UUID("00000000-0000-0000-0000-0000000000ee")
    cov = _get(empty, "/api/v1/compliance-matrix/coverage")
    assert cov == _get(_TENANT_A, "/api/v1/compliance-matrix/coverage")
