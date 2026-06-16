"""STORY-301 — AI system & agent registry tests.

AC coverage:
- An entry can be created with all required fields and retrieved by id.
- owner must be a non-empty named human; empty is rejected at the API boundary.
- Entries can be listed and filtered by tier, owner, and lifecycle_stage.
- Every create/update writes an immutable audit-trail row (who, what, when).
- A malformed entry (missing required field) is rejected.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSON as PG_JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy.types as sa_types

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]
PG_JSON.none_as_null = False

from database import Base, get_db  # noqa: E402
from models import GRCRegistryAudit, Tenant, User  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

from fastapi.testclient import TestClient  # noqa: E402
from auth import get_current_user  # noqa: E402
from main import app  # noqa: E402

from grc.registry import RegistryEntryCreate  # noqa: E402

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _seed_user() -> None:
    db = TestingSessionLocal()
    if db.query(Tenant).filter(Tenant.id == TENANT_ID).first() is None:
        db.add(Tenant(id=TENANT_ID, name="Acme", slug="acme-301"))
        db.add(
            User(
                id=USER_ID,
                tenant_id=TENANT_ID,
                email="owner@acme.test",
                role="operator",
                persona_role="risk_officer",
            )
        )
        db.commit()
    db.close()


def _fake_user() -> User:
    return User(
        id=USER_ID,
        tenant_id=TENANT_ID,
        email="owner@acme.test",
        role="operator",
        persona_role="risk_officer",
    )


@pytest.fixture()
def client():
    _seed_user()

    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _fake_user
    # Plain TestClient (no `with`) so the app lifespan/startup migrations — which
    # target the real DB, not SQLite — do not run. Matches the suite convention.
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _valid_payload(**over) -> dict:
    base = {
        "entry_type": "system",
        "name": "Claims Triage Agent",
        "owner": "Dr. Alice Chen",
        "version": "1.2.0",
        "purpose": "Triage inbound insurance claims",
        "data_sources": ["claims_db", "policy_docs"],
        "model_version": "claude-sonnet-4",
        "lifecycle_stage": "production",
        "deployment_status": "active",
        "domain": "healthcare",
    }
    base.update(over)
    return base


# ── Unit: payload validation ──────────────────────────────────────────────
@pytest.mark.unit
def test_create_payload_happy() -> None:
    p = RegistryEntryCreate(**_valid_payload())
    assert p.owner == "Dr. Alice Chen"
    assert p.entry_type == "system"


@pytest.mark.unit
def test_create_payload_blank_owner_rejected() -> None:
    with pytest.raises(ValueError):
        RegistryEntryCreate(**_valid_payload(owner="   "))


@pytest.mark.unit
def test_create_payload_missing_name_rejected() -> None:
    bad = _valid_payload()
    del bad["name"]
    with pytest.raises(ValueError):
        RegistryEntryCreate(**bad)


@pytest.mark.unit
def test_create_payload_bad_entry_type_rejected() -> None:
    with pytest.raises(ValueError):
        RegistryEntryCreate(**_valid_payload(entry_type="robot"))


# ── Integration: round-trip via the API ───────────────────────────────────
@pytest.mark.integration
def test_create_retrieve_roundtrip(client) -> None:
    r = client.post("/api/v1/grc/registry", json=_valid_payload())
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["owner"] == "Dr. Alice Chen"
    eid = created["id"]

    got = client.get(f"/api/v1/grc/registry/{eid}")
    assert got.status_code == 200
    assert got.json()["name"] == "Claims Triage Agent"
    assert got.json()["data_sources"] == ["claims_db", "policy_docs"]


@pytest.mark.integration
def test_blank_owner_rejected_at_api(client) -> None:
    r = client.post("/api/v1/grc/registry", json=_valid_payload(owner=""))
    assert r.status_code == 422


@pytest.mark.integration
def test_missing_required_field_rejected_at_api(client) -> None:
    bad = _valid_payload()
    del bad["owner"]
    r = client.post("/api/v1/grc/registry", json=bad)
    assert r.status_code == 422


@pytest.mark.integration
def test_list_and_filter(client) -> None:
    client.post(
        "/api/v1/grc/registry",
        json=_valid_payload(name="A", owner="Owner-A", lifecycle_stage="production"),
    )
    client.post(
        "/api/v1/grc/registry",
        json=_valid_payload(name="B", owner="Owner-B", lifecycle_stage="development"),
    )

    all_entries = client.get("/api/v1/grc/registry").json()
    assert len([e for e in all_entries if e["name"] in ("A", "B")]) == 2

    by_owner = client.get("/api/v1/grc/registry", params={"owner": "Owner-A"}).json()
    assert all(e["owner"] == "Owner-A" for e in by_owner)
    assert any(e["name"] == "A" for e in by_owner)

    by_stage = client.get(
        "/api/v1/grc/registry", params={"lifecycle_stage": "development"}
    ).json()
    assert all(e["lifecycle_stage"] == "development" for e in by_stage)


@pytest.mark.integration
def test_create_and_update_write_audit_rows(client) -> None:
    r = client.post("/api/v1/grc/registry", json=_valid_payload(name="Audited"))
    eid = r.json()["id"]

    upd = client.patch(
        f"/api/v1/grc/registry/{eid}", json={"purpose": "Updated purpose"}
    )
    assert upd.status_code == 200
    assert upd.json()["purpose"] == "Updated purpose"

    trail = client.get(f"/api/v1/grc/registry/{eid}/audit").json()
    actions = [row["action"] for row in trail]
    assert actions == ["create", "update"]
    # The update row records the diff (who/what/when).
    update_row = trail[1]
    assert "purpose" in update_row["changes"]
    assert update_row["changes"]["purpose"]["new"] == "Updated purpose"
    assert update_row["actor_email"] == "owner@acme.test"
    assert update_row["created_at"] is not None


@pytest.mark.integration
def test_audit_row_persisted_in_db(client) -> None:
    client.post("/api/v1/grc/registry", json=_valid_payload(name="DBCheck"))
    db = TestingSessionLocal()
    try:
        rows = (
            db.query(GRCRegistryAudit).filter(GRCRegistryAudit.action == "create").all()
        )
        assert len(rows) >= 1
    finally:
        db.close()
