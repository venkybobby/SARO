"""STORY-CHUB-011 — validation-status filtering for rule-pack data.

In-memory SQLite. Covers:
  AC-1  DRAFT_UNVALIDATED / RETIRED excluded from default customer views
  AC-2  filtering is server-side (get_matrix_rows), enforced regardless of client
  AC-3  internal personas (ai_auditor/admin) can reveal drafts with a badge;
        unprivileged personas' show_drafts request is silently ignored
  AC-4  LEGACY visible by default (flag on) with an internal-only pending badge
  Edge  NULL status fails closed (hidden); NIST rows unaffected; counts exclude drafts
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# The root conftest applies the Postgres->SQLite type shims before models import.
from auth import get_current_user
from config import settings
from database import Base, get_db
from main import app
from models import EUAIActRule, NISTControl, User
from services import rule_visibility as rv
from services.compliance_matrix_service import get_matrix_rows

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _seed(db):
    for tbl in (EUAIActRule, NISTControl):
        db.query(tbl).delete()
    db.add_all(
        [
            EUAIActRule(
                title="sme", article_number="A1", validation_status="SME_VALIDATED"
            ),
            EUAIActRule(
                title="legacy",
                article_number="A2",
                validation_status="LEGACY_UNREVIEWED",
            ),
            EUAIActRule(
                title="draft",
                article_number="A3",
                validation_status="DRAFT_UNVALIDATED",
            ),
            EUAIActRule(
                title="retired", article_number="A4", validation_status="RETIRED"
            ),
            EUAIActRule(
                title="nullstatus", article_number="A5", validation_status=None
            ),
            NISTControl(subcategory_id="N1", description="nist"),
        ]
    )
    db.commit()


def _eu_titles(rows):
    return {
        r["requirement_summary"] for r in rows if r["regulation_name"] == "EU AI Act"
    }


# ── policy unit ──────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_visibility_policy():
    assert rv.is_visible_by_default("SME_VALIDATED", include_legacy=True) is True
    assert rv.is_visible_by_default("LEGACY_UNREVIEWED", include_legacy=True) is True
    assert rv.is_visible_by_default("LEGACY_UNREVIEWED", include_legacy=False) is False
    assert rv.is_visible_by_default("DRAFT_UNVALIDATED", include_legacy=True) is False
    assert rv.is_visible_by_default("RETIRED", include_legacy=True) is False
    assert rv.is_visible_by_default(None, include_legacy=True) is False  # fail-closed


# ── service unit ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_default_view_hides_draft_retired_null():
    db = _Session()
    try:
        _seed(db)
        titles = _eu_titles(get_matrix_rows(db))
        assert titles == {"sme", "legacy"}  # draft, retired, null excluded
    finally:
        db.close()


@pytest.mark.unit
def test_show_drafts_reveals_all_with_badges():
    db = _Session()
    try:
        _seed(db)
        rows = [
            r
            for r in get_matrix_rows(db, show_drafts=True)
            if r["regulation_name"] == "EU AI Act"
        ]
        by_title = {r["requirement_summary"]: r["validation_badge"] for r in rows}
        assert by_title["draft"] == rv.BADGE_DRAFT
        assert by_title["retired"] == rv.BADGE_RETIRED
        assert by_title["legacy"] == rv.BADGE_PENDING_VALIDATION
        assert by_title["nullstatus"] == rv.BADGE_DRAFT  # fail-closed badge
        assert by_title["sme"] is None
    finally:
        db.close()


@pytest.mark.unit
def test_legacy_flag_off_hides_legacy(monkeypatch):
    db = _Session()
    try:
        _seed(db)
        monkeypatch.setattr(settings, "saro_show_legacy_rules", False)
        assert _eu_titles(get_matrix_rows(db)) == {"sme"}
    finally:
        db.close()


@pytest.mark.unit
def test_nist_rows_always_visible():
    db = _Session()
    try:
        _seed(db)
        rows = get_matrix_rows(db)
        assert any(r["regulation_name"] == "NIST AI RMF" for r in rows)
    finally:
        db.close()


# ── integration: persona gate ────────────────────────────────────────────────
def _user(persona):
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = f"{persona}@test.example"
    u.role = "operator"
    u.persona_role = persona
    u.tenant_id = uuid.uuid4()
    u.is_active = True
    u.read_only = False
    return u


def _client(user):
    def _get_db():
        db = _Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


@pytest.mark.integration
def test_endpoint_default_hides_drafts():
    with _Session() as s:
        _seed(s)
    r = _client(_user("compliance_lead")).get("/api/v1/compliance-matrix")
    assert r.status_code == 200
    titles = _eu_titles(r.json()["items"])
    assert "draft" not in titles and "retired" not in titles
    assert r.json()["showing_drafts"] is False


@pytest.mark.integration
def test_privileged_persona_can_show_drafts():
    with _Session() as s:
        _seed(s)
    r = _client(_user("ai_auditor")).get("/api/v1/compliance-matrix?show_drafts=true")
    assert r.status_code == 200
    assert r.json()["showing_drafts"] is True
    assert "draft" in _eu_titles(r.json()["items"])


@pytest.mark.integration
def test_unprivileged_show_drafts_is_ignored():
    with _Session() as s:
        _seed(s)
    # compliance_lead is NOT in the draft-toggle persona set -> silently forced off.
    r = _client(_user("compliance_lead")).get(
        "/api/v1/compliance-matrix?show_drafts=true"
    )
    assert r.status_code == 200
    assert r.json()["showing_drafts"] is False
    assert "draft" not in _eu_titles(r.json()["items"])


@pytest.mark.integration
def test_coverage_counts_exclude_drafts():
    with _Session() as s:
        _seed(s)
    r = _client(_user("ai_auditor")).get("/api/v1/compliance-matrix/coverage")
    assert r.status_code == 200
    eu = next(
        (f for f in r.json()["frameworks"] if f["framework"] == "EU AI Act"), None
    )
    # Only the 2 visible EU rows (sme, legacy) are counted, not draft/retired/null.
    assert eu is not None and eu["total_rules"] == 2
