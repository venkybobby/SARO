"""
SAR-013: EU AI Act AI System Inventory — test suite.

10 tests covering models, migration file, service logic, and router RBAC.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# 1. Model — AISystem has required columns
# ─────────────────────────────────────────────────────────────────────────────

def test_ai_system_model_has_required_fields():
    from models import AISystem
    mapper = AISystem.__mapper__
    col_names = {c.key for c in mapper.columns}
    for field in ("id", "tenant_id", "name", "eu_ai_act_risk_tier",
                  "last_audit_date", "current_risk_score", "is_active"):
        assert field in col_names, f"AISystem missing column: {field}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Model — SystemAudit junction table exists
# ─────────────────────────────────────────────────────────────────────────────

def test_system_audit_junction_table_exists():
    from models import SystemAudit
    mapper = SystemAudit.__mapper__
    col_names = {c.key for c in mapper.columns}
    assert "system_id" in col_names
    assert "audit_id" in col_names


# ─────────────────────────────────────────────────────────────────────────────
# 3. Migration file exists
# ─────────────────────────────────────────────────────────────────────────────

def test_migration_file_exists():
    migration = ROOT / "migrations" / "010_ai_system_inventory.sql"
    assert migration.exists(), f"Migration file not found: {migration}"


# ─────────────────────────────────────────────────────────────────────────────
# 4–6. Service — compute_audit_status
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_audit_status_never_audited():
    from services.system_service import compute_audit_status
    assert compute_audit_status(None) == "never_audited"


def test_compute_audit_status_current():
    from services.system_service import compute_audit_status
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    assert compute_audit_status(recent) == "current"


def test_compute_audit_status_overdue():
    from services.system_service import compute_audit_status
    old = datetime.now(timezone.utc) - timedelta(days=45)
    assert compute_audit_status(old) == "overdue"


# ─────────────────────────────────────────────────────────────────────────────
# Router tests — use FastAPI TestClient with dependency overrides
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(persona: str | None = None, role: str = "operator") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.role = role
    user.persona_role = persona
    return user


def _make_db_empty():
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []
    db.query.return_value = query
    return db


# ─────────────────────────────────────────────────────────────────────────────
# 7. GET /api/v1/systems returns 200 and a list
# ─────────────────────────────────────────────────────────────────────────────

def test_list_systems_returns_200():
    from fastapi.testclient import TestClient
    from main import app
    from auth import get_current_user
    from database import get_db

    user = _make_user()
    db = _make_db_empty()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/api/v1/systems")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────────────────────────────────────
# 8. POST /api/v1/systems returns 201
# ─────────────────────────────────────────────────────────────────────────────

def test_create_system_returns_201():
    from fastapi.testclient import TestClient
    from main import app
    from auth import get_current_user
    from database import get_db
    from models import AISystem

    user = _make_user()

    # Build a real AISystem instance to return from db.refresh
    system_instance = AISystem(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Test AI System",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = lambda obj: None  # no-op; system_instance already set

    # Capture the system added so refresh can point to it
    def fake_add(obj):
        # Copy id/created_at onto obj so system_to_dict works
        obj.id = system_instance.id
        obj.tenant_id = system_instance.tenant_id
        obj.created_at = system_instance.created_at
        obj.last_audit_date = None
        obj.description = None
        obj.system_owner = None
        obj.purpose = None
        obj.deployment_context = None
        obj.eu_ai_act_risk_tier = None
        obj.current_risk_score = None
        obj.is_active = True

    db.add = fake_add

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/api/v1/systems", json={"name": "Test AI System"})
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────────────────────────────────────
# 9. PATCH eu_ai_act_risk_tier forbidden for ai_auditor
# ─────────────────────────────────────────────────────────────────────────────

def test_risk_tier_forbidden_for_ai_auditor():
    from fastapi.testclient import TestClient
    from main import app
    from auth import get_current_user
    from database import get_db
    from models import AISystem

    user = _make_user(persona="ai_auditor")
    system_id = uuid.uuid4()

    existing = AISystem(
        id=system_id,
        tenant_id=user.tenant_id,
        name="Existing System",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.patch(
            f"/api/v1/systems/{system_id}",
            json={"eu_ai_act_risk_tier": "high"},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────────────────────────────────────
# 10. PATCH eu_ai_act_risk_tier allowed for compliance_lead
# ─────────────────────────────────────────────────────────────────────────────

def test_risk_tier_allowed_for_compliance_lead():
    from fastapi.testclient import TestClient
    from main import app
    from auth import get_current_user
    from database import get_db
    from models import AISystem

    user = _make_user(persona="compliance_lead")
    system_id = uuid.uuid4()

    existing = AISystem(
        id=system_id,
        tenant_id=user.tenant_id,
        name="Existing System",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    existing.description = None
    existing.system_owner = None
    existing.purpose = None
    existing.deployment_context = None
    existing.eu_ai_act_risk_tier = None
    existing.last_audit_date = None
    existing.current_risk_score = None
    existing.updated_at = None

    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q
    db.commit = MagicMock()
    db.refresh = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.patch(
            f"/api/v1/systems/{system_id}",
            json={"eu_ai_act_risk_tier": "high"},
        )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
