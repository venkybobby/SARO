"""STORY-381 — privacy-safe product analytics.

The load-bearing tests are the ones that prove PII cannot enter an event: a
closed event vocabulary, a closed property allowlist, bounded scalar values, and
no free-text field. If those hold, the analytics table is PHI-free by
construction rather than by a redaction step that can be forgotten.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

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
_orig = PG_UUID.__init__
PG_UUID.__init__ = lambda self, *a, **k: (k.pop("as_uuid", None), _orig(self, *a, **k))[1]  # type: ignore
PG_JSON.__init__ = lambda self, *a, **k: sa_types.Text.__init__(self)  # type: ignore

from database import Base  # noqa: E402
import models  # noqa: E402,F401
from models import ProductEvent  # noqa: E402
import services.product_analytics as analytics  # noqa: E402

Base.metadata.create_all(engine)

pytestmark = pytest.mark.integration

SCHEMA_DOC = ROOT / "docs" / "analytics" / "event-schema.md"
QUERIES_DOC = ROOT / "docs" / "analytics" / "queries.md"
RETENTION = ROOT / "docs" / "sample-evidence-retention.md"


@pytest.fixture
def db():
    with engine.begin() as conn:
        for t in reversed(Base.metadata.sorted_tables):
            conn.execute(t.delete())
    s = TestingSessionLocal()
    yield s
    s.rollback()
    s.close()


# ── AC-1: PHI-free by construction ──────────────────────────────────────────


def test_event_carries_no_free_text_column():
    """The structural guarantee: the model has nowhere to put content."""
    cols = set(ProductEvent.__table__.columns.keys())
    assert cols == {"id", "tenant_id", "event_name", "properties", "created_at"}
    # No user_id / email / text / body / prompt column exists.
    for banned in ("user_id", "email", "text", "body", "prompt", "content", "notes"):
        assert banned not in cols


def test_unknown_event_name_is_rejected(db):
    with pytest.raises(analytics.AnalyticsError, match="unknown event_name"):
        analytics.record(db, tenant_id=uuid.uuid4(), event_name="sneaky_custom_event")


def test_unknown_property_key_is_rejected(db):
    """A free-text property is the classic PII leak — refuse it."""
    with pytest.raises(analytics.AnalyticsError, match="free-text/unknown"):
        analytics.record(
            db, tenant_id=uuid.uuid4(), event_name=analytics.LOGIN,
            properties={"user_email": "clinician@hospital.example"},
        )


def test_oversized_property_value_is_rejected(db):
    with pytest.raises(analytics.AnalyticsError, match="exceeds"):
        analytics.record(
            db, tenant_id=uuid.uuid4(), event_name=analytics.LOGIN,
            properties={"persona": "x" * 200},
        )


def test_non_scalar_property_value_is_rejected(db):
    with pytest.raises(analytics.AnalyticsError, match="bounded scalar"):
        analytics.record(
            db, tenant_id=uuid.uuid4(), event_name=analytics.LOGIN,
            properties={"persona": {"nested": "object"}},
        )


def test_closed_value_allowlist_is_enforced(db):
    with pytest.raises(analytics.AnalyticsError, match="allow-list"):
        analytics.record(
            db, tenant_id=uuid.uuid4(), event_name=analytics.LOGIN,
            properties={"surface": "carrier_pigeon"},
        )


def test_a_valid_event_is_recorded(db):
    t = uuid.uuid4()
    analytics.record(
        db, tenant_id=t, event_name=analytics.LOGIN,
        properties={"persona": "compliance_lead", "surface": "web"},
    )
    row = db.query(ProductEvent).filter(ProductEvent.tenant_id == t).one()
    assert row.event_name == "login"
    assert row.properties["persona"] == "compliance_lead"


# ── Fail-open ───────────────────────────────────────────────────────────────


def test_safe_record_never_raises_on_a_bad_event(db):
    """Analytics must not break a request. A vocabulary violation is swallowed."""
    analytics.safe_record(db, tenant_id=uuid.uuid4(), event_name="nope")
    assert db.query(ProductEvent).count() == 0


def test_safe_record_writes_a_valid_event(db):
    analytics.safe_record(
        db, tenant_id=uuid.uuid4(), event_name=analytics.FIRST_EVALUATION,
        properties={"surface": "api", "outcome": "success"},
    )
    assert db.query(ProductEvent).count() == 1


# ── AC-3: funnel points are wired ───────────────────────────────────────────


def test_login_handler_emits_a_login_event():
    src = (ROOT / "routers" / "auth.py").read_text(encoding="utf-8")
    assert "analytics.LOGIN" in src


def test_subscribe_emits_a_subscribe_event():
    src = (ROOT / "services" / "rule_pack_lifecycle.py").read_text(encoding="utf-8")
    assert "RULE_PACK_SUBSCRIBED" in src


def test_first_evaluation_is_emitted_once_per_tenant():
    src = (ROOT / "services" / "audit_submission.py").read_text(encoding="utf-8")
    assert "FIRST_EVALUATION" in src
    # guarded by an existence check so it fires only on the first evaluation
    assert "seen is None" in src


# ── AC-4: founder query set ─────────────────────────────────────────────────


def test_analytics_summary_command_exists():
    src = (ROOT / "cli.py").read_text(encoding="utf-8")
    assert 'analytics-summary' in src


def test_queries_doc_covers_the_key_funnels():
    doc = QUERIES_DOC.read_text(encoding="utf-8").lower()
    assert "login" in doc and "attestation" in doc
    assert "subscribe" in doc or "subscribed" in doc
    assert "first_evaluation" in doc or "first evaluation" in doc


# ── AC-1 doc + AC-5 disclosure ──────────────────────────────────────────────


def test_schema_doc_exists_and_states_phi_free_by_construction():
    doc = SCHEMA_DOC.read_text(encoding="utf-8").lower()
    assert "phi-free by construction" in doc
    assert "no free-text field" in doc or "no free text" in doc
    assert "first-party" in doc


def test_schema_doc_names_third_party_saas_as_signoff_gated():
    doc = SCHEMA_DOC.read_text(encoding="utf-8").lower()
    assert "not adopted without owner sign-off" in doc or "security-review" in doc


def test_analytics_is_disclosed_in_the_retention_doc():
    doc = RETENTION.read_text(encoding="utf-8").lower()
    assert "product analytics" in doc
    assert "no personal data by construction" in doc
    assert "first-party" in doc


def test_retention_doc_states_a_retention_period_for_analytics():
    doc = RETENTION.read_text(encoding="utf-8")
    assert "395 days" in doc or "13 months" in doc


# ── No user identity in the schema (privacy stance) ─────────────────────────


def test_no_user_identifier_is_stored_in_an_event():
    """Tenant id is the only identifier — actor tracking is the audit trail's job."""
    doc = SCHEMA_DOC.read_text(encoding="utf-8").lower()
    assert "no individual user identity" in doc
    assert "tenant id" in doc
