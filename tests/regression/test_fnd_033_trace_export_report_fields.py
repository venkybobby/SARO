"""STORY-TRACE-006 (reviewer MAJOR): TRACE export endpoints read the real ScanReport fields.

`routers/trace_view.py` export endpoints read `report.risk_score` / `report.confidence`,
but `ScanReport` has no such columns — the real fields are `overall_risk_score` and
`confidence_score`. The JSON export silently returned null scores; the PDF export
raised AttributeError -> 500 whenever reportlab was installed (prod). STORY-TRACE-006
wired the Export buttons to these endpoints, exposing the bug to users.

This pins the fix: the JSON export carries the real (non-null) score/confidence, and
neither export endpoint 500s for an audit that has a report.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from main import app
from models import Audit, ScanReport, Tenant

pytestmark = [pytest.mark.regression, pytest.mark.integration]

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

TENANT = uuid.uuid4()
AUDIT = uuid.uuid4()


def _seed():
    db = _Session()
    db.add(Tenant(id=TENANT, name="A", slug="trace033"))
    db.add(
        Audit(
            id=AUDIT,
            tenant_id=TENANT,
            dataset_name="scan",
            sample_count=50,
            status="completed",
        )
    )
    db.add(
        ScanReport(
            id=uuid.uuid4(),
            audit_id=AUDIT,
            tenant_id=TENANT,
            report_json={},
            overall_risk_score=0.74,
            confidence_score=0.9,
        )
    )
    db.commit()
    db.close()


_seed()


def _client():
    class _U:
        id = uuid.uuid4()
        role = "operator"
        persona_role = None
        is_active = True
        read_only = False

    u = _U()
    u.tenant_id = TENANT
    app.dependency_overrides[get_db] = lambda: _Session()
    app.dependency_overrides[get_current_user] = lambda: u
    return TestClient(app, raise_server_exceptions=False)


def test_json_export_carries_the_real_risk_score():
    resp = _client().get(f"/api/v1/audit/{AUDIT}/export/json")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_score"] == 0.74, (
        "export must read overall_risk_score, not the absent risk_score"
    )
    assert body["confidence"] == 0.9


def test_pdf_export_does_not_500_for_an_audit_with_a_report():
    # With reportlab installed (prod) this exercises the report-rendering branch
    # that previously raised AttributeError; without it, the text/plain fallback.
    resp = _client().get(f"/api/v1/audit/{AUDIT}/export/pdf")
    assert resp.status_code == 200, resp.text
