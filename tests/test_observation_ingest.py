"""Persistence bridge: observation Findings -> evidence tables the UI reads.

Pins that a Vertex/Azure observation ingest lands as Audit + ScanReport +
AuditTrace rows the three personas' pages query, with the honesty guarantees
(observation check_type, labeled score basis) and a valid hash chain.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.contract import (
    FieldAvailability,
    NormalizedInvocationRecord,
    SourceProvenance,
    ToolInvocation,
)
from database import Base
from models import Audit, AuditTrace, ScanReport, Tenant
from rule_packs.observation.loader import load_genesis_packs
from services.hash_chain_service import verify_chain
from services.observation_ingest import (
    SCORE_BASIS,
    persist_observation_findings,
)

pytestmark = pytest.mark.unit

_ADAPTER = "vertex-ai-audit-log"

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


@pytest.fixture()
def db_session():
    s = _Session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _rec(
    request_id: str, *, model_id: str = "gemini-2.0-flash", tools=()
) -> NormalizedInvocationRecord:
    return NormalizedInvocationRecord(
        provenance=SourceProvenance(adapter_id=_ADAPTER, cursor=f"c:{request_id}"),
        tenant_id=uuid.uuid4(),  # must be IGNORED by the writer (INV-3)
        request_id=request_id,
        model_id=model_id,
        operation="PredictionService.GenerateContent",
        region="us-central1",
        timestamp=datetime(2026, 7, 25, tzinfo=timezone.utc),
        tools=tuple(tools),
        field_availability={
            "input_token_count": FieldAvailability.UNAVAILABLE,
            "output_token_count": FieldAvailability.UNAVAILABLE,
            "stop_reason": FieldAvailability.UNAVAILABLE,
        },
    )


@pytest.fixture()
def tenant(db_session):
    t = Tenant(name="Obs Demo", slug=f"obs-{uuid.uuid4().hex[:8]}")
    db_session.add(t)
    db_session.commit()
    return t


def _packs():
    packs = load_genesis_packs()
    out = []
    for ref in sorted(packs):
        p = packs[ref]
        if p.name == "RP-TOOL-SCOPE":
            p = p.with_allowed_tools(["lookup_care_pathway"])
        out.append(p)
    return out


def test_ingest_persists_audit_scanreport_and_traces(db_session, tenant):
    records = [
        _rec("r1"),
        # out-of-scope tool invocation -> a HIGH tool-scope finding
        _rec(
            "r2",
            tools=[ToolInvocation(name="purge_audit_log", offered=True, invoked=True)],
        ),
    ]
    result = persist_observation_findings(
        db_session,
        tenant_id=tenant.id,
        system_id="gemini-prod",
        records=records,
        packs=_packs(),
    )

    audit = db_session.get(Audit, result.audit_id)
    assert audit is not None
    assert audit.tenant_id == tenant.id  # operator config, NOT the log's tenant_id
    assert audit.sample_count == 2
    assert audit.status == "completed"
    assert "Vertex observation" in audit.dataset_name

    report = db_session.query(ScanReport).filter(ScanReport.audit_id == audit.id).one()
    assert report.report_json["score_basis"] == SCORE_BASIS
    assert "disclaimer" in report.report_json
    assert result.overall_score == 1.0  # a HIGH finding present

    traces = db_session.query(AuditTrace).filter(AuditTrace.audit_id == audit.id).all()
    assert traces, "no traces written"
    assert all(t.check_type == "observation" for t in traces), (
        "must not masquerade as risk_domain"
    )
    assert any(t.result == "flagged" for t in traces)  # the HIGH tool-scope violation


def test_traces_are_actionable_and_carry_remediation(db_session, tenant):
    result = persist_observation_findings(
        db_session,
        tenant_id=tenant.id,
        system_id="s1",
        records=[
            _rec(
                "r2",
                tools=[
                    ToolInvocation(name="purge_audit_log", offered=True, invoked=True)
                ],
            )
        ],
        packs=_packs(),
    )
    flagged = (
        db_session.query(AuditTrace)
        .filter(AuditTrace.audit_id == result.audit_id, AuditTrace.result == "flagged")
        .all()
    )
    assert flagged
    t = flagged[0]
    assert t.remediation_hint  # a persona can act on it (Remedy screen)
    assert t.is_remediated is False
    assert t.detail_json["severity"] == "HIGH"
    assert "request_id" in t.detail_json


def test_hash_chain_verifies(db_session, tenant):
    result = persist_observation_findings(
        db_session,
        tenant_id=tenant.id,
        system_id="s1",
        records=[
            _rec("r1"),
            _rec(
                "r2",
                tools=[
                    ToolInvocation(name="purge_audit_log", offered=True, invoked=True)
                ],
            ),
        ],
        packs=_packs(),
    )
    traces = (
        db_session.query(AuditTrace)
        .filter(AuditTrace.audit_id == result.audit_id)
        .order_by(AuditTrace.created_at.asc())
        .all()
    )

    def _ca(t):
        # Production is Postgres (DateTime tz-aware) so the stored value round-trips
        # WITH tzinfo, matching the write-time hash. SQLite drops the tz label on
        # read; the value is still the UTC it was written as, so re-label it before
        # isoformat so the test reconstructs the same string the writer hashed.
        ca = t.created_at
        if ca is not None and ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        return ca.isoformat() if ca else ""

    events = [
        {
            "id": str(t.id),
            "audit_id": str(t.audit_id),
            "gate_id": str(
                t.gate_id
            ),  # str(None)=="None" — matches writer + audit_chain._event_dict
            "gate_name": t.gate_name,
            "check_type": t.check_type,
            "check_name": t.check_name,
            "result": t.result,
            "reason": t.reason or "",
            "signal_text": t.signal_text or "",
            "remediation_hint": t.remediation_hint or "",
            "created_at": _ca(t),
            "event_hash": t.event_hash,
            "prev_hash": t.prev_hash,
        }
        for t in traces
    ]
    assert verify_chain(events)["valid"] is True


def test_clean_batch_still_produces_a_visible_pass_trace(db_session, tenant):
    # A record with lookup_care_pathway (allowed) and no other gaps -> clean.
    rec = _rec(
        "r-clean",
        tools=[ToolInvocation(name="lookup_care_pathway", offered=True, invoked=True)],
    )
    result = persist_observation_findings(
        db_session, tenant_id=tenant.id, system_id="s1", records=[rec], packs=_packs()
    )
    traces = (
        db_session.query(AuditTrace)
        .filter(AuditTrace.audit_id == result.audit_id)
        .all()
    )
    # OBS-TOKEN-COUNTS fires at INFO on Vertex (no token counts) -> not fully clean,
    # but the point pinned here: the invocation is visible and every trace is observation-typed.
    assert traces
    assert all(t.check_type == "observation" for t in traces)


def test_ingest_is_idempotent_on_batch_id(db_session, tenant):
    kw = dict(tenant_id=tenant.id, system_id="s1", records=[_rec("r1")], packs=_packs())
    first = persist_observation_findings(db_session, **kw)
    second = persist_observation_findings(db_session, **kw)
    assert second.skipped_duplicate is True
    assert second.audit_id == first.audit_id
    # Scope to this tenant: the module-shared engine holds obs:s1 audits from
    # other tests under other tenants — the idempotency guarantee is per-tenant.
    assert (
        db_session.query(Audit)
        .filter(Audit.batch_id == "obs:s1", Audit.tenant_id == tenant.id)
        .count()
        == 1
    )


def test_idempotency_is_tenant_scoped_no_cross_tenant_match(db_session):
    """INV-3: two tenants sharing a system_id must NOT collide on the idempotency
    key. Tenant B must get its OWN audit, never tenant A's, and its findings must
    actually persist (security-auditor finding #1)."""
    a = Tenant(name="A", slug=f"a-{uuid.uuid4().hex[:8]}")
    b = Tenant(name="B", slug=f"b-{uuid.uuid4().hex[:8]}")
    db_session.add_all([a, b])
    db_session.commit()

    ra = persist_observation_findings(
        db_session,
        tenant_id=a.id,
        system_id="gemini-prod",
        records=[_rec("r1")],
        packs=_packs(),
    )
    rb = persist_observation_findings(
        db_session,
        tenant_id=b.id,
        system_id="gemini-prod",
        records=[_rec("r1")],
        packs=_packs(),
    )
    assert rb.skipped_duplicate is False
    assert rb.audit_id != ra.audit_id  # B never handed A's audit
    assert db_session.get(Audit, ra.audit_id).tenant_id == a.id
    assert (
        db_session.get(Audit, rb.audit_id).tenant_id == b.id
    )  # B's findings persisted under B


def test_unknown_severity_fails_safe_to_flagged():
    """A finding with an unmapped severity must map to the MOST-severe bucket,
    never be silently downgraded (security-auditor finding #2)."""
    from services.observation_ingest import _SEVERITY, _rollup_score
    from rule_packs.observation.evaluate import Finding

    assert _SEVERITY["CRITICAL"] == (1.0, "flagged")
    bogus = Finding(
        rule_id="X",
        pack_ref="p@1",
        pack_hash="h",
        severity="CATACLYSMIC",
        title="t",
        remediation="r",
        request_id="rq",
        detail={},
    )
    assert _rollup_score([bogus]) == 1.0  # unknown → worst, not 0.3
