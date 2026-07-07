"""STORY-COV-002 — live observation-checkpoint emission (COV-001 AC-1, un-deferred).

SARO is push-model: a completed audit IS a live observation. emit_observation() turns each
audit on every live path into a coalesced heartbeat, with an opportunistic gap sweep.

Covers:
  emit core   coalescing per bucket (idempotent within a window); distinct buckets; INV-2
              token-guard opaques free text; opportunistic sweep opens a gap for a quiet
              system; sweep is throttled to fresh checkpoints; sweep is fail-open + flag-gated.
  wiring      GRC orchestrator, batch scan, and SDK ingest each emit through real code, and
              the audit path is fail-open when emission raises.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Audit, ObservationCheckpoint, ObservationGap, User
import services.observation_coverage_service as cov

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

# Non-exponent-like UUID (avoid SQLite NUMERIC affinity coercion).
_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fb")
_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _reset(db):
    for tbl in (ObservationCheckpoint, ObservationGap, Audit):
        db.query(tbl).delete()
    db.commit()


# ── emit core: coalescing ─────────────────────────────────────────────────────
@pytest.mark.unit
def test_emit_coalesces_within_bucket():
    db = _Session()
    try:
        _reset(db)
        first = cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="sdk-ingest",
            observed_at=_NOW,
            sweep=False,
        )
        # Same bucket (< bucket_seconds later) → idempotent no-op.
        dup = cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="sdk-ingest",
            observed_at=_NOW + timedelta(seconds=5),
            sweep=False,
        )
        assert first is not None and dup is None
        assert db.query(ObservationCheckpoint).count() == 1
    finally:
        db.close()


@pytest.mark.unit
def test_emit_distinct_buckets_record_separately():
    db = _Session()
    try:
        _reset(db)
        cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="sdk-ingest",
            observed_at=_NOW,
            sweep=False,
        )
        # A later bucket (> bucket_seconds) → a distinct heartbeat.
        later = cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="sys-1",
            adapter_id="sdk-ingest",
            observed_at=_NOW + timedelta(seconds=120),
            sweep=False,
        )
        assert later is not None
        assert db.query(ObservationCheckpoint).count() == 2
    finally:
        db.close()


# ── emit core: INV-2 token guard ──────────────────────────────────────────────
@pytest.mark.unit
def test_safe_ident_opaques_free_text():
    # Token-safe values pass through; free text / PII collapses to an opaque surrogate.
    assert cov._safe_ident("claude", fallback="unknown") == "claude"
    assert cov._safe_ident("grc-evaluation", fallback="unknown") == "grc-evaluation"
    assert cov._safe_ident("", fallback="unknown") == "unknown"
    opaque = cov._safe_ident("SSN 123-45-6789 patient note", fallback="unknown")
    assert opaque.startswith("op_") and " " not in opaque and len(opaque) <= 255


@pytest.mark.unit
def test_emit_never_stores_free_text_system_id():
    """INV-2 end-to-end: a free-text system_id is stored as an opaque token, never verbatim."""
    db = _Session()
    try:
        _reset(db)
        cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="Jane Doe — SSN 111-22-3333",
            adapter_id="batch-scan",
            observed_at=_NOW,
            sweep=False,
        )
        stored = db.query(ObservationCheckpoint).one()
        assert stored.system_id.startswith("op_")
        assert "SSN" not in stored.system_id and " " not in stored.system_id
    finally:
        db.close()


# ── emit core: opportunistic sweep ────────────────────────────────────────────
@pytest.mark.unit
def test_emit_sweep_opens_gap_for_quiet_system():
    db = _Session()
    try:
        _reset(db)
        # A previously-observed system goes quiet (last heartbeat 1h ago, cadence 300s).
        cov.record_checkpoint(
            db,
            tenant_id=_TENANT,
            system_id="quiet-sys",
            adapter_id="sdk-ingest",
            watermark_position="p0",
            watermark_timestamp=_NOW - timedelta(hours=1),
        )
        # A different system emits now, with the sweep on → the quiet system's gap opens.
        cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="busy-sys",
            adapter_id="sdk-ingest",
            observed_at=_NOW,
            sweep=True,
        )
        gaps = db.query(ObservationGap).filter(ObservationGap.gap_end.is_(None)).all()
        assert len(gaps) == 1
        assert gaps[0].system_id == "quiet-sys" and gaps[0].cause_class == cov.UNKNOWN
    finally:
        db.close()


@pytest.mark.unit
def test_emit_sweep_only_on_fresh_checkpoint(monkeypatch):
    """The sweep is throttled to fresh checkpoints — a coalesced (deduped) emit does not sweep."""
    db = _Session()
    try:
        _reset(db)
        calls = {"n": 0}

        def _counting_detect(db, **kw):
            calls["n"] += 1
            return []

        monkeypatch.setattr(cov, "detect_gaps", _counting_detect)
        # Fresh checkpoint → sweeps once.
        cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="s",
            adapter_id="a",
            observed_at=_NOW,
            sweep=True,
        )
        # Same bucket → deduped → NO sweep.
        cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="s",
            adapter_id="a",
            observed_at=_NOW + timedelta(seconds=1),
            sweep=True,
        )
        assert calls["n"] == 1
    finally:
        db.close()


@pytest.mark.unit
def test_emit_sweep_is_fail_open(monkeypatch):
    """A sweep failure must not fail the emit (which must not fail the audit)."""
    db = _Session()
    try:
        _reset(db)

        def _boom(db, **kw):
            raise RuntimeError("sweep exploded")

        monkeypatch.setattr(cov, "detect_gaps", _boom)
        cp = cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="s",
            adapter_id="a",
            observed_at=_NOW,
            sweep=True,
        )
        assert cp is not None  # emit still succeeded despite the sweep blowing up
    finally:
        db.close()


# ── wiring: shared stubs ──────────────────────────────────────────────────────
class _StubReport:
    status = "completed"
    engine_version = "test-engine"
    rule_pack_hash = "deadbeef"
    confidence_score = 0.9

    class mit_coverage:  # noqa: N801 — mirrors the real nested attribute access
        score = 0.5

    class fixed_delta:  # noqa: N801
        delta = 0.1

    class bayesian_scores:  # noqa: N801
        overall = 12.0

    def model_dump(self, mode=None):
        return {}


class _StubEngine:
    def __init__(self, db):
        pass

    def run_audit(self, payload, audit_id):
        return _StubReport()

    def run_output_audit(self, *, audit_id, raw_output, prompt, source_model):
        return _StubReport()


def _capture_emit(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        "services.observation_coverage_service.emit_observation",
        lambda db, **kw: calls.append(kw),
    )
    return calls


def _user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.tenant_id = _TENANT
    u.role = "operator"
    u.persona_role = "ai_auditor"
    u.is_active = True
    u.read_only = False
    return u


# ── wiring: GRC orchestrator path ─────────────────────────────────────────────
@pytest.mark.integration
def test_grc_path_emits(monkeypatch):
    db = _Session()
    try:
        _reset(db)
        monkeypatch.setattr(
            "grc.orchestrator.run_audit",
            lambda *a, **k: {"findings": [], "gate_recommendation": "PASS"},
        )
        calls = _capture_emit(monkeypatch)
        from grc.orchestrator import run_audit_by_id

        run_audit_by_id(db, tenant_id=_TENANT, output_id="out-x")
        assert calls and calls[0]["adapter_id"] == "grc-evaluation"
        assert calls[0]["system_id"] == "unknown"  # no evidence record seeded
    finally:
        db.close()


@pytest.mark.integration
def test_grc_path_is_fail_open_on_emit_error(monkeypatch):
    """Emission raising must not break the evaluation (fail-open NFR)."""
    db = _Session()
    try:
        _reset(db)
        monkeypatch.setattr(
            "grc.orchestrator.run_audit",
            lambda *a, **k: {"findings": [], "gate_recommendation": "PASS"},
        )

        def _boom(db, **kw):
            raise RuntimeError("emit exploded")

        monkeypatch.setattr(
            "services.observation_coverage_service.emit_observation", _boom
        )
        from grc.orchestrator import run_audit_by_id

        result = run_audit_by_id(db, tenant_id=_TENANT, output_id="out-y")
        assert result.get("gate_recommendation") == "PASS"  # audit still returned
    finally:
        db.close()


# ── wiring: batch scan path ───────────────────────────────────────────────────
@pytest.mark.integration
def test_scan_batch_emits(monkeypatch):
    from schemas import BatchIn, SampleIn

    db = _Session()
    try:
        _reset(db)
        monkeypatch.setattr("routers.scan.SARoEngine", _StubEngine)
        monkeypatch.setattr("routers.scan._persist_traces", lambda *a, **k: None)
        monkeypatch.setattr(
            "routers.scan._maybe_dispatch_risk_notification", lambda **k: None
        )
        calls = _capture_emit(monkeypatch)
        from routers.scan import scan_batch

        # Min 50 samples (internal SARO methodology); the stub engine ignores content.
        payload = BatchIn(
            dataset_name="orders-bot",
            samples=[SampleIn(text=f"s{i}") for i in range(50)],
        )
        scan_batch(payload, _user(), db)
        assert calls and calls[0]["adapter_id"] == "batch-scan"
        assert calls[0]["system_id"] == "orders-bot"
    finally:
        db.close()


# ── wiring: SDK ingest path ───────────────────────────────────────────────────
@pytest.mark.integration
def test_ingest_path_emits(monkeypatch):
    db = _Session()
    try:
        _reset(db)
        audit_id = uuid.uuid4()
        db.add(
            Audit(
                id=audit_id,
                tenant_id=_TENANT,
                dataset_name="Ingest:claude",
                sample_count=1,
                status="running",
                created_at=_NOW,
            )
        )
        db.commit()

        # The background task opens its own session — redirect it to our in-memory engine.
        def _fake_get_db():
            s = _Session()
            try:
                yield s
            finally:
                s.close()

        monkeypatch.setattr("database.get_db", _fake_get_db)
        monkeypatch.setattr("routers.ingest.SARoEngine", _StubEngine)
        monkeypatch.setattr("routers.scan._persist_traces", lambda *a, **k: None)
        calls = _capture_emit(monkeypatch)
        from routers.ingest import _run_audit_background

        _run_audit_background(audit_id, "prompt", "output", "claude")
        assert calls and calls[0]["adapter_id"] == "sdk-ingest"
        assert calls[0]["system_id"] == "claude"
    finally:
        db.close()


# ── Fix 3: quiet-tenant coverage report must not read as attested 100% ─────────
@pytest.mark.unit
def test_quiet_window_is_not_attested():
    """A window with zero observations reports observation_events=0, coverage_attested=False,
    and a caveat — the examiner-facing artifact must never imply un-observed visibility."""
    db = _Session()
    try:
        _reset(db)
        rep = cov.coverage_report(
            db, _TENANT, "sys-quiet", _NOW - timedelta(hours=1), _NOW
        )
        assert rep["observation_events"] == 0
        assert rep["coverage_attested"] is False
        assert rep["caveat"] and "vacuous" in rep["caveat"]
    finally:
        db.close()


@pytest.mark.unit
def test_observed_window_is_attested():
    """With at least one observation in the window, coverage is attested and the caveat clears."""
    db = _Session()
    try:
        _reset(db)
        cov.emit_observation(
            db,
            tenant_id=_TENANT,
            system_id="sys-live",
            adapter_id="sdk-ingest",
            observed_at=_NOW - timedelta(minutes=30),
            sweep=False,
        )
        rep = cov.coverage_report(
            db, _TENANT, "sys-live", _NOW - timedelta(hours=1), _NOW
        )
        assert rep["observation_events"] == 1
        assert rep["coverage_attested"] is True
        assert rep["caveat"] is None
    finally:
        db.close()
