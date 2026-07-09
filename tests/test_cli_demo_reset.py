"""STORY-410 — `saro demo reset` structural demo-tenant-only guard.

Covers:
  AC-4.1  refuses (no delete) unless the tenant's slug is in DEMO_TENANT_SLUGS —
          no flag combination bypasses this
  AC-4.2  requires --yes; without it, prints a preview and deletes nothing
  AC-4.3  two-tenant isolation: resetting the demo tenant never touches another
          tenant's rows (security-relevant given the prior cross-tenant leak finding)
  AC-4.4  reset -> re-ingest of the same corpus/seed reproduces a first-run ingest
"""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import cli as cli_module
import scripts.demo_corpus_builder as builder
from database import Base
from _sqlite_for_update_shim import install as _install_for_update_shim
from models import (
    Audit,
    AuditEvent,
    AuditMetadata,
    AuditTrace,
    Disposition,
    Notification,
    ObservationCheckpoint,
    ObservationGap,
    ScanReport,
    Tenant,
    User,
)

_REPO = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO / "scripts" / "demo_manifest.yaml"

_DEMO_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000d1")
_DEMO_USER = uuid.UUID("00000000-0000-0000-0000-0000000000d2")
_OTHER_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000d3")
_OTHER_USER = uuid.UUID("00000000-0000-0000-0000-0000000000d4")

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


# SQLite does not enforce foreign keys (or cascade deletes) unless explicitly told
# to per-connection. demo_reset()'s bulk .delete() of Audit relies on the DB-level
# ON DELETE CASCADE declared in models.py (ScanReport/AuditMetadata/AuditTrace) to
# clean up the audit family — this must be turned on for the test to actually prove
# that cascade fires, matching real Postgres's always-on FK enforcement.
@event.listens_for(_engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _manifest() -> dict:
    return builder.load_manifest(_MANIFEST_PATH)


def _clean_db() -> None:
    db = _Session()
    for tbl in (
        ObservationGap,
        ObservationCheckpoint,
        Disposition,
        AuditEvent,
        Notification,
        ScanReport,
        AuditTrace,
        AuditMetadata,
        Audit,
    ):
        db.query(tbl).delete()
    db.query(User).delete()
    db.query(Tenant).delete()
    db.add(Tenant(id=_DEMO_TENANT, name="SARO Demo Tenant", slug="saro-demo"))
    db.add(
        User(id=_DEMO_USER, tenant_id=_DEMO_TENANT, email="demo-reset-test@example.com")
    )
    db.add(Tenant(id=_OTHER_TENANT, name="Some Real Client", slug="acme-corp"))
    db.add(
        User(
            id=_OTHER_USER,
            tenant_id=_OTHER_TENANT,
            email="other-reset-test@example.com",
        )
    )
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def _db(monkeypatch):
    _clean_db()
    monkeypatch.setattr(cli_module, "_session_factory", lambda: _Session)
    _install_for_update_shim(monkeypatch)
    yield


def _seed_tenant_data(tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    """Seed one row per tenant-scoped table `demo reset` touches, INCLUDING the
    Audit family (Audit -> ScanReport/AuditMetadata/AuditTrace via DB-level
    ON DELETE CASCADE) — the highest-risk table given the prior cross-tenant
    timeline leak finding this guard exists to prevent. Returns the seeded
    audit_id so callers can assert on it directly."""
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    audit_id = uuid.uuid4()
    db = _Session()
    try:
        db.add(
            ObservationCheckpoint(
                tenant_id=tenant_id,
                system_id="claude",
                adapter_id="bedrock",
                watermark_position=f"s3:seed:{tenant_id}",
                watermark_timestamp=ts,
            )
        )
        db.add(
            ObservationGap(
                tenant_id=tenant_id,
                system_id="claude",
                adapter_id="bedrock",
                gap_start=ts,
                gap_end=ts + datetime.timedelta(hours=1),
            )
        )
        db.add(Disposition(tenant_id=tenant_id, rule_id="r1", gate_id="g1"))
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type="disposition_action",
                event_data={"seed": True},
            )
        )
        db.add(
            Notification(tenant_id=tenant_id, type="system", title="seed", body="seed")
        )
        db.add(
            Audit(
                id=audit_id,
                tenant_id=tenant_id,
                user_id=user_id,
                sample_count=1,
                status="completed",
                prompt_text="seed prompt",
                raw_output_text="seed output",
            )
        )
        db.commit()
        db.add(
            ScanReport(
                audit_id=audit_id,
                tenant_id=tenant_id,
                report_json={"seed": True},
            )
        )
        db.add(
            AuditMetadata(audit_id=audit_id, source_model="claude", vertical="general")
        )
        db.add(
            AuditTrace(
                audit_id=audit_id,
                tenant_id=tenant_id,
                gate_id=3,
                gate_name="Risk Classification (MIT Taxonomy)",
                check_type="risk_domain",
                check_name="Privacy & Security",
                result="flagged",
                event_hash=f"seed-hash-{audit_id}",
            )
        )
        db.commit()
    finally:
        db.close()
    return audit_id


# ── AC-4.1: structural guard — no bypass exists ───────────────────────────────
def test_refuses_non_demo_tenant():
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli, ["demo", "reset", "--tenant", str(_OTHER_TENANT), "--yes"]
    )
    assert result.exit_code != 0
    assert "not in the demo-tenant allowlist" in result.output

    db = _Session()
    try:
        assert db.get(Tenant, _OTHER_TENANT) is not None
    finally:
        db.close()


def test_no_flag_bypasses_the_demo_tenant_guard():
    """There is no --force or equivalent escape hatch (AC-4.1)."""
    params = {p.name for p in cli_module.demo_reset.params}
    assert "force" not in params
    assert params == {"tenant", "yes"}


# ── AC-4.2: requires --yes ─────────────────────────────────────────────────────
def test_requires_yes_flag_preview_only():
    _seed_tenant_data(_DEMO_TENANT, _DEMO_USER)
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli, ["demo", "reset", "--tenant", str(_DEMO_TENANT)]
    )
    assert result.exit_code == 0, result.output
    assert "Would delete" in result.output
    assert "Pass --yes" in result.output

    db = _Session()
    try:
        assert (
            db.query(ObservationCheckpoint).filter_by(tenant_id=_DEMO_TENANT).count()
            == 1
        )
    finally:
        db.close()


# ── AC-4.3: two-tenant isolation ──────────────────────────────────────────────
def test_tenant_isolation_reset_leaves_other_tenant_untouched():
    """Security-relevant given the prior cross-tenant timeline leak finding.

    Seeds the highest-risk table family too: Audit (+ its DB-cascaded children
    ScanReport/AuditMetadata/AuditTrace), AuditEvent, and Notification — not just
    the coverage/disposition tables — so this proves both that demo_reset's cascade
    actually clears the Audit family for the demo tenant AND that the other
    tenant's Audit/AuditTrace/AuditEvent/Notification rows survive untouched.
    """
    demo_audit_id = _seed_tenant_data(_DEMO_TENANT, _DEMO_USER)
    other_audit_id = _seed_tenant_data(_OTHER_TENANT, _OTHER_USER)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli, ["demo", "reset", "--tenant", str(_DEMO_TENANT), "--yes"]
    )
    assert result.exit_code == 0, result.output

    db = _Session()
    try:
        assert (
            db.query(ObservationCheckpoint).filter_by(tenant_id=_DEMO_TENANT).count()
            == 0
        )
        assert db.query(ObservationGap).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        assert db.query(Disposition).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        assert db.query(AuditEvent).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        assert db.query(Notification).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        assert db.query(Audit).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        # Cascade proof: the demo audit's children are gone too, not just the parent row.
        assert db.query(ScanReport).filter_by(audit_id=demo_audit_id).count() == 0
        assert db.query(AuditMetadata).filter_by(audit_id=demo_audit_id).count() == 0
        assert db.query(AuditTrace).filter_by(audit_id=demo_audit_id).count() == 0

        assert (
            db.query(ObservationCheckpoint).filter_by(tenant_id=_OTHER_TENANT).count()
            == 1
        )
        assert db.query(ObservationGap).filter_by(tenant_id=_OTHER_TENANT).count() == 1
        assert db.query(Disposition).filter_by(tenant_id=_OTHER_TENANT).count() == 1
        assert db.query(AuditEvent).filter_by(tenant_id=_OTHER_TENANT).count() == 1
        assert db.query(Notification).filter_by(tenant_id=_OTHER_TENANT).count() == 1
        assert db.query(Audit).filter_by(tenant_id=_OTHER_TENANT).count() == 1
        assert db.query(ScanReport).filter_by(audit_id=other_audit_id).count() == 1
        assert db.query(AuditMetadata).filter_by(audit_id=other_audit_id).count() == 1
        assert db.query(AuditTrace).filter_by(audit_id=other_audit_id).count() == 1
    finally:
        db.close()


# ── AC-4.4: reset -> re-ingest reproduces a first-run ingest ─────────────────
@pytest.mark.integration
def test_reset_then_reingest_matches_first_run(tmp_path):
    manifest = _manifest()
    summary = builder.build_corpus_to_dir(manifest, tmp_path, seed=42)
    win = manifest["window"]
    ingest_args = [
        "ingest",
        "--source",
        str(tmp_path),
        "--tenant",
        str(_DEMO_TENANT),
        "--window",
        f"{win['start']}..{win['end']}",
        "--account-id",
        summary.account_id,
        "--region",
        summary.region,
        "--cadence-seconds",
        str(int(manifest["cadence_seconds"])),
        "--json",
    ]
    runner = CliRunner()

    first = runner.invoke(cli_module.cli, ingest_args)
    assert first.exit_code == 0, first.output
    import json as _json

    first_out = _json.loads(first.output)

    reset = runner.invoke(
        cli_module.cli, ["demo", "reset", "--tenant", str(_DEMO_TENANT), "--yes"]
    )
    assert reset.exit_code == 0, reset.output

    db = _Session()
    try:
        assert db.query(Audit).filter_by(tenant_id=_DEMO_TENANT).count() == 0
        assert (
            db.query(ObservationCheckpoint).filter_by(tenant_id=_DEMO_TENANT).count()
            == 0
        )
    finally:
        db.close()

    second = runner.invoke(cli_module.cli, ingest_args)
    assert second.exit_code == 0, second.output
    second_out = _json.loads(second.output)

    assert second_out["findings_by_category"] == first_out["findings_by_category"]
    assert second_out["audits_submitted"] == first_out["audits_submitted"]
    assert len(second_out["gaps"]) == len(first_out["gaps"])
    assert second_out["coverage_attested"] == first_out["coverage_attested"]
