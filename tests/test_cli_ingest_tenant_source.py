"""STORY-408 AC-5.1 — `saro ingest --tenant <t>` resolves the tenant's source
config automatically; `--source` override retained for demo/local use.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import cli as cli_module
import scripts.demo_corpus_builder as builder
from adapters.bedrock.source import LocalLogStore
from database import Base
from _sqlite_for_update_shim import install as _install_for_update_shim
from models import (
    Audit,
    AuditMetadata,
    AuditTrace,
    ObservationCheckpoint,
    ObservationGap,
    ScanReport,
    Tenant,
    TenantLogSourceConfig,
    User,
)

_REPO = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO / "scripts" / "demo_manifest.yaml"

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
_USER = uuid.UUID("00000000-0000-0000-0000-0000000000c2")
_ROLE_ARN = "arn:aws:iam::999888777666:role/SaroCrossAccountRole"
_EXTERNAL_ID = "a" * 32

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _manifest() -> dict:
    return builder.load_manifest(_MANIFEST_PATH)


def _clean_db(with_config: bool, enabled: bool = True) -> None:
    db = _Session()
    for tbl in (
        ObservationGap,
        ObservationCheckpoint,
        ScanReport,
        AuditTrace,
        AuditMetadata,
        Audit,
        TenantLogSourceConfig,
    ):
        db.query(tbl).delete()
    db.query(User).delete()
    db.query(Tenant).delete()
    db.add(
        Tenant(id=_TENANT, name="Cross Account Test Tenant", slug="cross-account-test")
    )
    db.add(User(id=_USER, tenant_id=_TENANT, email="cross-account-test@example.com"))
    if with_config:
        db.add(
            TenantLogSourceConfig(
                tenant_id=_TENANT,
                role_arn=_ROLE_ARN,
                external_id=_EXTERNAL_ID,
                bucket="summitcare-bedrock-logs",
                prefix="",
                region="us-east-1",
                kms_key_arn=None,
                enabled=enabled,
            )
        )
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def _db(monkeypatch):
    _clean_db(with_config=False)
    monkeypatch.setattr(cli_module, "_session_factory", lambda: _Session)
    _install_for_update_shim(monkeypatch)
    yield


def test_no_source_no_config_refuses():
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "ingest",
            "--tenant",
            str(_TENANT),
            "--window",
            "2026-01-01T00:00:00Z..2026-01-02T00:00:00Z",
        ],
    )
    assert result.exit_code != 0
    assert "no log source config" in result.output


def test_disabled_config_refuses():
    _clean_db(with_config=True, enabled=False)
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "ingest",
            "--tenant",
            str(_TENANT),
            "--window",
            "2026-01-01T00:00:00Z..2026-01-02T00:00:00Z",
        ],
    )
    assert result.exit_code != 0
    assert "disabled" in result.output


@pytest.mark.integration
def test_no_source_resolves_tenant_config_and_ingests(tmp_path, monkeypatch):
    _clean_db(with_config=True, enabled=True)
    manifest = _manifest()
    builder.build_corpus_to_dir(manifest, tmp_path, seed=42)

    # Fake S3LogStore.for_tenant that proves the tenant config was actually
    # resolved and used (real STS/S3 wiring is covered by
    # tests/test_cross_account_s3_store.py) while reusing the demo corpus via
    # a LocalLogStore, so this test stays a pure CLI-wiring check.
    calls = []

    def _fake_for_tenant(config, *, sts_client=None, s3_client_override=None):
        calls.append(config)
        return LocalLogStore(tmp_path)

    monkeypatch.setattr(
        cli_module.S3LogStore, "for_tenant", staticmethod(_fake_for_tenant)
    )

    win = manifest["window"]
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "ingest",
            "--tenant",
            str(_TENANT),
            "--window",
            f"{win['start']}..{win['end']}",
            "--cadence-seconds",
            str(int(manifest["cadence_seconds"])),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["objects_discovered"] > 0
    assert len(calls) == 1
    assert calls[0].bucket == "summitcare-bedrock-logs"
    assert calls[0].account_id == "999888777666"


@pytest.mark.integration
def test_source_override_bypasses_tenant_config(tmp_path):
    _clean_db(with_config=True, enabled=True)
    manifest = _manifest()
    summary = builder.build_corpus_to_dir(manifest, tmp_path, seed=42)
    win = manifest["window"]

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "ingest",
            "--source",
            str(tmp_path),
            "--tenant",
            str(_TENANT),
            "--window",
            f"{win['start']}..{win['end']}",
            "--account-id",
            summary.account_id,
            "--region",
            summary.region,
            "--cadence-seconds",
            str(int(manifest["cadence_seconds"])),
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["source"] == str(tmp_path)
