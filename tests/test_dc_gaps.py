"""
Tests for SARO-DC-001 and SARO-DC-002 (Design-Choice Gap stories).

SARO-DC-001: signal_text on AuditTrace — modal trigger signal per domain.
SARO-DC-002: top_sample_ids on AuditTrace + navigation endpoint.

All tests run without a live database — engine tests use in-memory state,
schema/router tests use Pydantic and mock DB sessions.
"""
from __future__ import annotations

import os
import sys
import uuid
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_engine():
    from engine import SARoEngine
    db = MagicMock()
    db.query.return_value.all.return_value = []
    db.rollback = MagicMock()
    return SARoEngine(db)


def _run_batch_with_domain_text(engine, texts: list[str], n_safe: int = 50):
    """Run a batch with specified flagged texts padded with safe samples."""
    from engine import AuditConfigIn, BatchIn, SampleIn
    samples = [SampleIn(sample_id=f"f{i}", text=t) for i, t in enumerate(texts)]
    for i in range(n_safe):
        samples.append(SampleIn(sample_id=f"s{i}", text="safe neutral text"))
    batch = BatchIn.model_construct(
        batch_id="dc-test",
        dataset_name="dc-test",
        samples=samples,
        config=AuditConfigIn.model_construct(
            min_samples=1,
            confidence_threshold=0.95,
            incident_top_k=3,
            frameworks=["EU AI Act", "NIST AI RMF"],
        ),
    )
    return engine.run_audit(batch, uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-001: signal_text in _traces dict
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalTextInTraces:

    def test_gate3_domain_traces_have_signal_text_key(self):
        """Every Gate 3 domain trace dict must contain a signal_text key."""
        engine = _build_engine()
        _run_batch_with_domain_text(engine, ["biometric surveillance"] * 5)
        gate3_traces = [t for t in engine.get_traces() if t["gate_id"] == 3]
        assert gate3_traces, "Expected Gate 3 traces"
        for t in gate3_traces:
            assert "signal_text" in t, f"signal_text missing from trace: {t['check_name']}"

    def test_gate3_flagged_domain_has_non_null_signal_text(self):
        """A flagged Gate 3 domain trace must have a non-None signal_text."""
        engine = _build_engine()
        # 'hate racist' triggers Discrimination & Toxicity
        _run_batch_with_domain_text(engine, ["hate racist toxic content"] * 5)
        flagged = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "flagged"
        ]
        assert flagged, "Expected at least one flagged Gate 3 domain"
        for t in flagged:
            assert t["signal_text"] is not None, f"signal_text is None for flagged domain {t['check_name']}"
            assert len(t["signal_text"]) <= 500

    def test_gate3_pass_domain_has_null_signal_text(self):
        """Gate 3 domains with no flags should have signal_text=None."""
        engine = _build_engine()
        _run_batch_with_domain_text(engine, ["biometric"] * 3)
        passing = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "pass"
        ]
        assert passing, "Expected some passing Gate 3 domains"
        for t in passing:
            assert t["signal_text"] is None

    def test_gate3_signal_text_is_modal_signal_not_text(self):
        """signal_text must be a signal/keyword identifier, not raw matched text."""
        engine = _build_engine()
        # 'ssn' triggers Privacy & Security, 'hate' triggers Discrimination
        _run_batch_with_domain_text(engine, ["ssn hate hate hate racist"] * 3)
        flagged = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "flagged"
        ]
        for t in flagged:
            st = t["signal_text"]
            assert st is not None
            assert len(st) <= 500

    def test_gate4_traces_have_signal_text_key(self):
        """Gate 4 compliance rule traces must have signal_text = rule_id."""
        engine = _build_engine()
        # 'hack exploit malware' strongly triggers Malicious Use → Gate 4 rules
        _run_batch_with_domain_text(engine, ["hack exploit malware virus phish"] * 10)
        gate4_triggered = [
            t for t in engine.get_traces()
            if t["gate_id"] == 4 and t["result"] == "triggered"
        ]
        for t in gate4_triggered:
            assert "signal_text" in t
            assert t["signal_text"] is not None
            assert len(t["signal_text"]) <= 500

    def test_gate1_gate2_traces_have_signal_text_key(self):
        """Gate 1 and 2 traces include signal_text key (may be None)."""
        engine = _build_engine()
        _run_batch_with_domain_text(engine, ["safe"] * 2)
        for t in engine.get_traces():
            if t["gate_id"] in (1, 2):
                assert "signal_text" in t


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-001: AuditTraceOut schema
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditTraceOutSchema:

    def test_audit_trace_out_has_signal_text_field(self):
        """AuditTraceOut must declare signal_text as a nullable field."""
        from schemas import AuditTraceOut
        fields = AuditTraceOut.model_fields
        assert "signal_text" in fields, "signal_text missing from AuditTraceOut"

    def test_audit_trace_out_signal_text_default_none(self):
        """signal_text defaults to None for backward compatibility."""
        from schemas import AuditTraceOut
        field = AuditTraceOut.model_fields["signal_text"]
        assert field.default is None

    def test_audit_trace_out_accepts_null_signal_text(self):
        """AuditTraceOut validates cleanly when signal_text is None."""
        from schemas import AuditTraceOut
        data = {
            "id": str(uuid.uuid4()),
            "audit_id": str(uuid.uuid4()),
            "gate_id": 1,
            "gate_name": "Data Quality",
            "check_type": "gate_result",
            "check_name": "Data Quality",
            "result": "pass",
            "reason": "ok",
            "detail_json": None,
            "remediation_hint": None,
            "signal_text": None,
            "top_sample_ids": None,
            "is_remediated": False,
            "remediated_at": None,
            "created_at": "2026-05-20T10:00:00",
        }
        out = AuditTraceOut.model_validate(data)
        assert out.signal_text is None

    def test_audit_trace_out_accepts_signal_text_value(self):
        """AuditTraceOut round-trips a non-null signal_text."""
        from schemas import AuditTraceOut
        data = {
            "id": str(uuid.uuid4()),
            "audit_id": str(uuid.uuid4()),
            "gate_id": 3,
            "gate_name": "Risk Classification (MIT Taxonomy)",
            "check_type": "risk_domain",
            "check_name": "Privacy & Security",
            "result": "flagged",
            "reason": "5 signals detected",
            "detail_json": None,
            "remediation_hint": None,
            "signal_text": "ssn_pattern",
            "top_sample_ids": ["s1", "s2"],
            "is_remediated": False,
            "remediated_at": None,
            "created_at": "2026-05-20T10:00:00",
        }
        out = AuditTraceOut.model_validate(data)
        assert out.signal_text == "ssn_pattern"


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-002: top_sample_ids in _traces dict
# ─────────────────────────────────────────────────────────────────────────────

class TestTopSampleIdsInTraces:

    def test_gate3_flagged_trace_has_top_sample_ids(self):
        """Flagged Gate 3 domain traces must have a non-empty top_sample_ids list."""
        engine = _build_engine()
        # 'hate racist' triggers Discrimination & Toxicity
        _run_batch_with_domain_text(engine, ["hate racist toxic content"] * 5)
        flagged = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "flagged"
        ]
        assert flagged
        for t in flagged:
            assert "top_sample_ids" in t
            assert isinstance(t["top_sample_ids"], list)
            assert len(t["top_sample_ids"]) >= 1

    def test_gate3_pass_trace_has_null_top_sample_ids(self):
        """Passing Gate 3 domains have top_sample_ids=None."""
        engine = _build_engine()
        _run_batch_with_domain_text(engine, ["biometric"] * 3)
        passing = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "pass"
        ]
        assert passing
        for t in passing:
            assert t["top_sample_ids"] is None

    def test_top_sample_ids_capped_at_10(self):
        """top_sample_ids must contain at most 10 entries even with many flagged samples."""
        engine = _build_engine()
        # 25 flagged samples with Discrimination & Toxicity keywords
        _run_batch_with_domain_text(engine, ["hate racist discriminat toxic sexist"] * 25)
        flagged = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "flagged"
        ]
        for t in flagged:
            if t["top_sample_ids"]:
                assert len(t["top_sample_ids"]) <= 10

    def test_top_sample_ids_are_strings(self):
        """All entries in top_sample_ids must be string sample_id values."""
        engine = _build_engine()
        _run_batch_with_domain_text(engine, ["hate racist toxic"] * 8)
        flagged = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3 and t["result"] == "flagged"
        ]
        for t in flagged:
            if t["top_sample_ids"]:
                for sid in t["top_sample_ids"]:
                    assert isinstance(sid, str), f"Expected str sample_id, got {type(sid)}"

    def test_gate4_traces_have_null_top_sample_ids(self):
        """Gate 4 compliance rule traces have top_sample_ids=None."""
        engine = _build_engine()
        # Use keywords that trigger Gate 4 rules
        _run_batch_with_domain_text(engine, ["hack exploit malware virus"] * 10)
        gate4 = [t for t in engine.get_traces() if t["gate_id"] == 4]
        for t in gate4:
            assert "top_sample_ids" in t
            assert t["top_sample_ids"] is None


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-002: AuditTraceOut schema — top_sample_ids
# ─────────────────────────────────────────────────────────────────────────────

class TestTopSampleIdsSchema:

    def test_audit_trace_out_has_top_sample_ids_field(self):
        from schemas import AuditTraceOut
        assert "top_sample_ids" in AuditTraceOut.model_fields

    def test_top_sample_ids_default_is_none(self):
        from schemas import AuditTraceOut
        field = AuditTraceOut.model_fields["top_sample_ids"]
        assert field.default is None

    def test_top_sample_ids_round_trips(self):
        from schemas import AuditTraceOut
        data = {
            "id": str(uuid.uuid4()),
            "audit_id": str(uuid.uuid4()),
            "gate_id": 3,
            "gate_name": "Risk Classification (MIT Taxonomy)",
            "check_type": "risk_domain",
            "check_name": "AI System Safety",
            "result": "flagged",
            "reason": "8 signals",
            "detail_json": None,
            "remediation_hint": None,
            "signal_text": "biometric",
            "top_sample_ids": ["s1", "s2", "s3"],
            "is_remediated": False,
            "remediated_at": None,
            "created_at": "2026-05-20T10:00:00",
        }
        out = AuditTraceOut.model_validate(data)
        assert out.top_sample_ids == ["s1", "s2", "s3"]


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-002: PaginatedSampleFindingOut schema
# ─────────────────────────────────────────────────────────────────────────────

class TestPaginatedSampleFindingOutSchema:

    def test_schema_exists(self):
        from schemas import PaginatedSampleFindingOut
        assert PaginatedSampleFindingOut is not None

    def test_schema_fields(self):
        from schemas import PaginatedSampleFindingOut
        fields = PaginatedSampleFindingOut.model_fields
        assert "results" in fields
        assert "page" in fields
        assert "page_size" in fields
        assert "total" in fields

    def test_total_is_optional(self):
        from schemas import PaginatedSampleFindingOut
        field = PaginatedSampleFindingOut.model_fields["total"]
        assert field.default is None

    def test_empty_results(self):
        from schemas import PaginatedSampleFindingOut
        out = PaginatedSampleFindingOut(results=[], page=1, page_size=50, total=0)
        assert out.results == []
        assert out.total == 0

    def test_second_page_has_null_total(self):
        """On page > 1, total is not populated (None by default)."""
        from schemas import PaginatedSampleFindingOut
        out = PaginatedSampleFindingOut(results=[], page=2, page_size=50)
        assert out.total is None


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-002: Navigation endpoint — unit tests without live DB
# ─────────────────────────────────────────────────────────────────────────────

class TestSampleFindingsNavigationEndpoint:

    def _make_trace(self, trace_id, audit_id, tenant_id, check_name="Privacy & Security"):
        from models import AuditTrace
        t = MagicMock(spec=AuditTrace)
        t.id = trace_id
        t.audit_id = audit_id
        t.check_name = check_name
        return t

    def _make_audit(self, audit_id, tenant_id):
        from models import Audit
        a = MagicMock(spec=Audit)
        a.id = audit_id
        a.tenant_id = tenant_id
        return a

    def _make_finding(self, audit_id, domain, sample_id, weight=0.8):
        from models import SampleFinding
        import datetime
        f = MagicMock(spec=SampleFinding)
        f.id = uuid.uuid4()
        f.audit_id = audit_id
        f.sample_id = sample_id
        f.domain = domain
        f.matched_signal = "keyword:biometric"
        f.matched_text_fragment = "biometric ***"
        f.weight = weight
        f.created_at = datetime.datetime(2026, 5, 20, 10, 0, 0)
        return f

    def test_endpoint_registered_in_router(self):
        """Navigation endpoint must be registered on the traces router."""
        from routers.traces import router
        paths = [r.path for r in router.routes]
        assert any("sample-findings" in p for p in paths), (
            f"sample-findings endpoint not found. Routes: {paths}"
        )

    def test_returns_404_for_unknown_trace(self):
        from routers.traces import get_sample_findings_for_trace
        from fastapi import HTTPException

        db = MagicMock()
        db.get.return_value = None  # trace not found

        user = MagicMock()
        user.tenant_id = uuid.uuid4()

        with pytest.raises(HTTPException) as exc_info:
            get_sample_findings_for_trace(
                trace_id=uuid.uuid4(),
                current_user=user,
                db=db,
                page=1,
                page_size=50,
            )
        assert exc_info.value.status_code == 404

    def test_returns_404_for_different_tenant(self):
        """Tenant B cannot access Tenant A's trace."""
        from routers.traces import get_sample_findings_for_trace
        from fastapi import HTTPException

        trace_id = uuid.uuid4()
        audit_id = uuid.uuid4()
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()

        db = MagicMock()
        db.get.return_value = self._make_trace(trace_id, audit_id, tenant_a_id)

        # Audit belongs to tenant A — query returns None for tenant B
        db.query.return_value.filter.return_value.first.return_value = None

        user = MagicMock()
        user.tenant_id = tenant_b_id

        with pytest.raises(HTTPException) as exc_info:
            get_sample_findings_for_trace(
                trace_id=trace_id,
                current_user=user,
                db=db,
                page=1,
                page_size=50,
            )
        assert exc_info.value.status_code == 404

    def test_returns_empty_results_for_non_gate3_trace(self):
        """Gate 1/2/4 traces return HTTP 200 with results=[] (no SampleFindings)."""
        from routers.traces import get_sample_findings_for_trace
        import datetime

        trace_id = uuid.uuid4()
        audit_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        trace = self._make_trace(trace_id, audit_id, tenant_id, check_name="Data Quality")
        audit = self._make_audit(audit_id, tenant_id)

        # Build a DB mock where the full query chain returns empty
        findings_chain = MagicMock()
        findings_chain.count.return_value = 0
        findings_chain.offset.return_value.limit.return_value.all.return_value = []

        audit_chain = MagicMock()
        audit_chain.first.return_value = audit

        db = MagicMock()
        db.get.return_value = trace

        def query_side_effect(model):
            from models import Audit, SampleFinding
            if model is Audit:
                q = MagicMock()
                q.filter.return_value = audit_chain
                return q
            if model is SampleFinding:
                # Real query: .filter(A, B).order_by(C, D) → base_q
                q = MagicMock()
                q.filter.return_value.order_by.return_value = findings_chain
                return q
            return MagicMock()

        db.query.side_effect = query_side_effect

        result = get_sample_findings_for_trace(
            trace_id=trace_id,
            current_user=MagicMock(tenant_id=tenant_id),
            db=db,
            page=1,
            page_size=50,
        )
        assert result.results == []
        assert result.page == 1

    def test_paginated_response_structure(self):
        """Verify the paginated response includes page, page_size, total on page 1."""
        from schemas import PaginatedSampleFindingOut

        out = PaginatedSampleFindingOut(
            results=[],
            page=1,
            page_size=50,
            total=8,
        )
        assert out.page == 1
        assert out.page_size == 50
        assert out.total == 8

    def test_total_not_populated_on_page_2(self):
        from schemas import PaginatedSampleFindingOut
        out = PaginatedSampleFindingOut(results=[], page=2, page_size=50)
        assert out.total is None


# ─────────────────────────────────────────────────────────────────────────────
# SARO-DC-001: PII safety — signal_text stores pattern name not raw value
# ─────────────────────────────────────────────────────────────────────────────

class TestSignalTextPiiSafety:

    def test_signal_text_does_not_equal_raw_pii_fragment(self):
        """
        signal_text on a Privacy & Security trace must be a signal identifier,
        not a raw PII value like '123-45-6789'.
        """
        engine = _build_engine()
        # 'ssn' and 'private password' trigger Privacy & Security
        _run_batch_with_domain_text(engine, ["ssn private password credit card 123-45-6789"] * 5)
        privacy_traces = [
            t for t in engine.get_traces()
            if t["gate_id"] == 3
            and t["check_name"] == "Privacy & Security"
            and t["result"] == "flagged"
        ]
        for t in privacy_traces:
            st = t.get("signal_text", "")
            if st:
                assert "123-45-6789" not in st
                assert "123456789" not in st

    def test_signal_text_length_enforced(self):
        """signal_text must be <= 500 characters."""
        engine = _build_engine()
        _run_batch_with_domain_text(engine, ["biometric"] * 5)
        for t in engine.get_traces():
            if t.get("signal_text"):
                assert len(t["signal_text"]) <= 500


# ─────────────────────────────────────────────────────────────────────────────
# Model field existence checks (no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestModelFields:

    def test_audit_trace_model_has_signal_text(self):
        from models import AuditTrace
        from sqlalchemy import inspect as sa_inspect
        cols = {c.key for c in sa_inspect(AuditTrace).mapper.column_attrs}
        assert "signal_text" in cols, f"signal_text not in AuditTrace columns: {cols}"

    def test_audit_trace_model_has_top_sample_ids(self):
        from models import AuditTrace
        from sqlalchemy import inspect as sa_inspect
        cols = {c.key for c in sa_inspect(AuditTrace).mapper.column_attrs}
        assert "top_sample_ids" in cols, f"top_sample_ids not in AuditTrace columns: {cols}"

    def test_signal_text_is_nullable(self):
        from models import AuditTrace
        from sqlalchemy import inspect as sa_inspect
        col = sa_inspect(AuditTrace).mapper.columns["signal_text"]
        assert col.nullable is True

    def test_top_sample_ids_is_nullable(self):
        from models import AuditTrace
        from sqlalchemy import inspect as sa_inspect
        col = sa_inspect(AuditTrace).mapper.columns["top_sample_ids"]
        assert col.nullable is True


# ─────────────────────────────────────────────────────────────────────────────
# database.py: _SAFE_ALTER_COLS includes audit_traces
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseSafeAlterCols:

    def test_audit_traces_in_safe_alter_cols(self):
        """audit_traces must be in _SAFE_ALTER_COLS so columns are never dropped."""
        import database
        assert "audit_traces" in database._SAFE_ALTER_COLS

    def test_signal_text_in_safe_alter_cols(self):
        import database
        assert "signal_text" in database._SAFE_ALTER_COLS["audit_traces"]

    def test_top_sample_ids_in_safe_alter_cols(self):
        import database
        assert "top_sample_ids" in database._SAFE_ALTER_COLS["audit_traces"]

    def test_audit_traces_expected_cols_includes_new_fields(self):
        """_APP_TABLE_EXPECTED_COLS must list both new columns for drift detection."""
        import database
        cols = database._APP_TABLE_EXPECTED_COLS["audit_traces"]
        assert "signal_text" in cols
        assert "top_sample_ids" in cols
