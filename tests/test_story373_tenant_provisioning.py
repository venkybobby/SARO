"""STORY-373 — idempotent tenant provisioning + onboarding playbook.

The behaviours that matter are the refusals: a re-run must not mutate, an
email collision must not be adopted, and the BAA gate must be enforced in code
rather than in a checklist someone skips under time pressure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── in-memory SQLite, mirroring tests/test_chub004_readiness.py ─────────────
import sqlalchemy.types as sa_types  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.dialects.postgresql import JSON as PG_JSON  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine)

_orig_uuid_init = PG_UUID.__init__


def _sqlite_uuid_init(self, *args, **kwargs):
    kwargs.pop("as_uuid", None)
    _orig_uuid_init(self, *args, **kwargs)


PG_UUID.__init__ = _sqlite_uuid_init  # type: ignore[method-assign]
PG_JSON.__init__ = lambda self, *a, **kw: sa_types.Text.__init__(self)  # type: ignore[method-assign]

from database import Base  # noqa: E402
import models  # noqa: E402,F401
from models import Tenant, TenantLogSourceConfig, User  # noqa: E402
from services.tenant_provisioning import (  # noqa: E402
    BAAGateNotConfirmed,
    ProvisioningError,
    generate_password,
    provision_tenant,
    verify_isolation,
)

Base.metadata.create_all(engine)

pytestmark = pytest.mark.integration

PLAYBOOK = ROOT / "docs" / "ops" / "tenant-onboarding.md"


@pytest.fixture
def db():
    # Every test starts from an empty schema. The shared StaticPool connection
    # means a prior test's committed rows would otherwise leak in and make the
    # slug/email-collision assertions order-dependent.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


def _provision(db, slug="acme", email=None, baa=True, **over):
    return provision_tenant(
        db,
        name=over.pop("name", f"{slug} Health"),
        slug=slug,
        admin_email=email or f"admin@{slug}.example.com",
        baa_confirmed=baa,
        actor="operator@saro.test.example.com",
        **over,
    )


# ── AC-1: creation ──────────────────────────────────────────────────────────


def test_provisioning_creates_tenant_admin_and_placeholder(db):
    result = _provision(db, slug="acme")

    assert result.created is True
    assert db.query(Tenant).filter(Tenant.slug == "acme").count() == 1

    admin = db.query(User).filter(User.email == "admin@acme.example.com").first()
    assert admin is not None
    assert admin.role == "super_admin"
    assert admin.tenant_id == result.tenant_id

    placeholder = (
        db.query(TenantLogSourceConfig)
        .filter(TenantLogSourceConfig.tenant_id == result.tenant_id)
        .first()
    )
    assert placeholder is not None
    assert placeholder.enabled is False, "placeholder must not be live on creation"


def test_generated_password_is_returned_once_and_never_serialized(db):
    result = _provision(db, slug="acme")
    assert result.generated_password, "operator needs the credential once"
    assert "generated_password" not in result.summary(), (
        "the password must not travel into logs, JSON output, or audit metadata"
    )
    assert result.generated_password not in str(result.summary())


def test_generated_passwords_are_unique_and_not_a_default():
    assert generate_password() != generate_password()
    assert len(generate_password()) >= 24


# ── AC-1: idempotency, the property operators actually rely on ─────────────


def test_reprovisioning_the_same_slug_writes_nothing(db):
    first = _provision(db, slug="acme")
    second = _provision(db, slug="acme")

    assert second.created is False
    assert second.tenant_id == first.tenant_id
    assert "tenant" in second.already_existed
    assert db.query(Tenant).filter(Tenant.slug == "acme").count() == 1


def test_reprovisioning_does_not_reset_the_admin_password(db):
    """FND-058's failure mode: a re-run silently rotating a live credential."""
    _provision(db, slug="acme")
    admin = db.query(User).filter(User.email == "admin@acme.example.com").first()
    original_hash = admin.hashed_password

    second = _provision(db, slug="acme")

    db.refresh(admin)
    assert admin.hashed_password == original_hash, "a re-run rotated a live password"
    assert second.generated_password is None


def test_reprovisioning_does_not_reenable_a_disabled_log_source(db):
    """A re-run must not undo deliberate configuration."""
    result = _provision(db, slug="acme")
    cfg = (
        db.query(TenantLogSourceConfig)
        .filter(TenantLogSourceConfig.tenant_id == result.tenant_id)
        .first()
    )
    cfg.bucket = "customer-owned-bucket"
    cfg.enabled = True
    db.flush()

    _provision(db, slug="acme")

    db.refresh(cfg)
    assert cfg.bucket == "customer-owned-bucket"
    assert cfg.enabled is True


# ── AC-1: refusals ──────────────────────────────────────────────────────────


def test_existing_admin_email_is_refused_not_adopted(db):
    """FND-058 again: matching on email and reassigning is how accounts get hijacked."""
    _provision(db, slug="acme", email="shared@example.com")

    with pytest.raises(ProvisioningError, match="already exists"):
        _provision(db, slug="beta", email="shared@example.com")


def test_email_collision_does_not_leave_a_half_created_tenant(db):
    _provision(db, slug="acme", email="shared@example.com")
    before = db.query(Tenant).count()

    with pytest.raises(ProvisioningError):
        _provision(db, slug="beta", email="shared@example.com")

    db.rollback()
    assert db.query(Tenant).count() == before, "a refused provisioning left a tenant behind"


# ── AC-3: the BAA gate is code, not a checklist ─────────────────────────────


def test_provisioning_refuses_without_baa_confirmation(db):
    with pytest.raises(BAAGateNotConfirmed) as exc:
        _provision(db, slug="acme", baa=False)
    assert "INV-6" in str(exc.value)
    assert db.query(Tenant).filter(Tenant.slug == "acme").count() == 0


def test_baa_refusal_names_the_artifact_to_check(db):
    with pytest.raises(BAAGateNotConfirmed) as exc:
        _provision(db, slug="acme", baa=False)
    assert "compliance/baa/" in str(exc.value), "tell the operator where to look"


# ── AC-2: isolation check ───────────────────────────────────────────────────


def test_new_tenant_sees_no_other_tenants_rows(db):
    _provision(db, slug="first")
    second = _provision(db, slug="second")

    result = verify_isolation(db, second.tenant_id)
    assert result["isolated"] is True
    assert result["meaningful"] is True, "another tenant exists, so the check has teeth"


def test_isolation_check_reports_when_it_cannot_prove_anything(db):
    """A lone tenant cannot demonstrate isolation — say so rather than pass quietly."""
    only = _provision(db, slug="only")
    result = verify_isolation(db, only.tenant_id)
    assert result["meaningful"] is False


def test_isolation_check_counts_evidence_tables(db):
    result = verify_isolation(db, _provision(db, slug="acme").tenant_id)
    for table in ("audits", "scan_reports", "audit_events"):
        assert table in result["row_counts"]


# ── AC-4: audited ───────────────────────────────────────────────────────────


def test_provisioning_writes_an_admin_audit_event(db, monkeypatch):
    calls = {}

    def _spy(_db, **kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("services.self_audit.record_privileged", _spy)
    result = _provision(db, slug="acme")

    assert calls, "provisioning was not audited (STORY-366)"
    assert calls["action_class"] == "ADMIN_ACTION"
    assert calls["target_id"] == str(result.tenant_id)
    assert calls["metadata"]["operation"] == "provision_tenant"


def test_audit_metadata_never_contains_the_generated_password(db, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "services.self_audit.record_privileged", lambda _db, **kw: calls.update(kw)
    )
    result = _provision(db, slug="acme")
    assert result.generated_password not in str(calls)


# ── AC-3: the playbook ──────────────────────────────────────────────────────


def test_playbook_exists_with_the_baa_stop_step():
    doc = PLAYBOOK.read_text(encoding="utf-8")
    assert "BAA" in doc
    assert "STOP" in doc.upper()
    assert "INV-6" in doc


def test_playbook_documents_invocation_verification_and_rollback():
    doc = PLAYBOOK.read_text(encoding="utf-8").lower()
    for section in ("prerequisites", "verification", "rollback"):
        assert section in doc, f"playbook missing a {section} section"
    assert "saro tenant provision" in doc


def test_playbook_states_the_credential_is_shown_once():
    doc = PLAYBOOK.read_text(encoding="utf-8").lower()
    assert "once" in doc and "password" in doc
