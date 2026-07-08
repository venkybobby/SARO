"""STORY-407 — Demo Corpus Builder (synthetic Bedrock invocation logs).

Covers the story's all-or-nothing verification bar:
  AC-1.1/1.2  every builder record validates against the doc-grounded schema fixture
  AC-2.1/2.3  S3 key layout mirrors the adapter's discovery; hourly multi-record objects
  AC-3.1/3.2  determinism (byte-identical for a seed; seed re-rolls ids, not placement)
  AC-4.1      E2E: build -> STORY-406 adapter ingest -> engine eval -> exactly the COVERED
              planted findings fire (UC-1/2/6) + zero on clean traffic (UC-3/4/5 planted,
              documented not-yet-firing)
  AC-5.1      the deliberate observation gap surfaces in the coverage attestation
  AC-6.1      synthetic-provenance markers on every record
  guard       the source-reader addition keeps the adapters path STORY-336-clean

The E2E also exercises adapters/bedrock/source.py (the S3-layout reader that turns the
builder's output into the (cursor, raw) pairs replay_backfill consumes).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import jsonschema
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import scripts.demo_corpus_builder as builder
from adapters.bedrock import (
    LocalLogStore,
    discover_object_keys,
    iter_backfill_records,
    replay_backfill,
)
from adapters.bedrock.records import BedrockAdapterConfig
from database import Base
from models import (
    Audit,
    AuditMetadata,
    ObservationCheckpoint,
    ObservationGap,
    ScanReport,
)
import services.observation_coverage_service as cov

_REPO = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO / "scripts" / "demo_manifest.yaml"
_SCHEMA_PATH = (
    _REPO / "tests" / "fixtures" / "bedrock" / "model_invocation_log.schema.json"
)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fc")
_USER = uuid.UUID("00000000-0000-0000-0000-0000000000fd")

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)


def _manifest() -> dict:
    return builder.load_manifest(_MANIFEST_PATH)


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _db():
    db = _Session()
    for tbl in (
        ObservationGap,
        ObservationCheckpoint,
        ScanReport,
        AuditMetadata,
        Audit,
    ):
        db.query(tbl).delete()
    db.commit()
    return db


# ── AC-1: schema fidelity ────────────────────────────────────────────────────
@pytest.mark.unit
def test_schema_fixture_is_valid_and_doc_grounded():
    schema = _schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    # AC-1.2: provenance must record the AWS source URL + retrieval date + schemaVersion.
    prov = schema["$comment"]
    assert "docs.aws.amazon.com/bedrock" in prov
    assert "2026-07-08" in prov and "1.0" in prov


@pytest.mark.unit
def test_every_builder_record_matches_schema():
    recs, _ = builder.generate_corpus(_manifest(), seed=42)
    validator = jsonschema.Draft202012Validator(_schema())
    assert recs
    for r in recs:
        errors = sorted(validator.iter_errors(r.record), key=str)
        assert not errors, f"record {r.request_id} fails schema: {errors[:1]}"
        # Demo records are always inline-body (never S3-externalized).
        assert "inputBodyJson" in r.record["input"]
        assert "outputBodyJson" in r.record["output"]


# ── AC-6: synthetic provenance ───────────────────────────────────────────────
@pytest.mark.unit
def test_synthetic_provenance_on_every_record():
    manifest = _manifest()
    recs, summary = builder.generate_corpus(manifest, seed=42)
    assert summary.account_id == "999888777666"  # synthetic account marker
    for r in recs:
        meta = r.record["requestMetadata"]
        assert meta["environment"] == "demo-synthetic"
        assert meta["source"] == "saro-evidence-corpus"
        assert r.record["accountId"] == "999888777666"


# ── AC-2: S3 key layout + hourly batching ────────────────────────────────────
@pytest.mark.unit
def test_s3_key_layout_and_hourly_batching(tmp_path):
    manifest = _manifest()
    summary = builder.build_corpus_to_dir(manifest, tmp_path, seed=42)
    keys = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.json.gz")]
    assert keys
    prefix = (
        f"AWSLogs/{summary.account_id}/BedrockModelInvocationLogs/{summary.region}/"
    )
    for k in keys:
        assert k.startswith(prefix) and k.endswith(".json.gz")
    # AC-2.3: at least one hourly object batches multiple records (multi-record parsing).
    store = LocalLogStore(tmp_path)
    per_object = {}
    for cursor, _raw in iter_backfill_records(store, sorted(keys)):
        obj = cursor.rsplit(":L", 1)[0]
        per_object[obj] = per_object.get(obj, 0) + 1
    assert max(per_object.values()) >= 2


@pytest.mark.unit
def test_observation_gap_has_no_objects_with_traffic_on_both_sides(tmp_path):
    manifest = _manifest()
    builder.build_corpus_to_dir(manifest, tmp_path, seed=42)
    # The declared gap hour (2026-07-07/03) has no object; the hours on both sides do.
    base = (
        tmp_path
        / "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/2026/07/07"
    )
    assert not (base / "03").exists()
    assert (base / "02").exists() and (base / "04").exists()


# ── AC-3: determinism ────────────────────────────────────────────────────────
@pytest.mark.unit
def test_determinism_byte_identical_for_same_seed():
    manifest = _manifest()
    r1, s1 = builder.generate_corpus(manifest, seed=42)
    r2, s2 = builder.generate_corpus(manifest, seed=42)
    o1 = builder.build_objects(r1, s1.account_id, s1.region)
    o2 = builder.build_objects(r2, s2.account_id, s2.region)
    assert o1 == o2  # keys AND gzipped bytes identical (fixed gzip mtime)


@pytest.mark.unit
def test_seed_changes_ids_not_planted_placement():
    manifest = _manifest()
    _, s42 = builder.generate_corpus(manifest, seed=42)
    _, s99 = builder.generate_corpus(manifest, seed=99)
    p42 = {p.use_case: p for p in s42.planted}
    p99 = {p.use_case: p for p in s99.planted}
    assert p42.keys() == p99.keys()
    for uc in p42:
        assert p42[uc].request_id != p99[uc].request_id  # ids re-rolled
        assert p42[uc].at == p99[uc].at  # placement unchanged
        assert p42[uc].expected == p99[uc].expected


# ── source.py reader (STORY-406/-407 discovery half) ─────────────────────────
@pytest.mark.unit
def test_source_reader_roundtrip(tmp_path):
    manifest = _manifest()
    summary = builder.build_corpus_to_dir(manifest, tmp_path, seed=42)
    store = LocalLogStore(tmp_path)
    win_s = builder._parse_iso(manifest["window"]["start"])
    win_e = builder._parse_iso(manifest["window"]["end"])
    keys = discover_object_keys(
        store,
        account_id=summary.account_id,
        region=summary.region,
        window_start=win_s,
        window_end=win_e,
    )
    assert len(keys) == summary.object_count
    corpus = list(iter_backfill_records(store, keys))
    assert len(corpus) == summary.record_count
    cursors = [c for c, _ in corpus]
    assert len(set(cursors)) == len(cursors)  # unique, monotonic stream cursors


@pytest.mark.unit
def test_source_reader_is_guard_clean():
    """The new source reader keeps the scanned adapters path STORY-336-clean."""
    from grc.guards import external_model as g

    assert "adapters" in g.PRODUCT_PACKAGE_DIRS
    violations = g.scan_paths([_REPO / "adapters"], repo_root=_REPO)
    assert violations == [], f"adapters path not guard-clean: {violations}"


# ── AC-4.1 + AC-5.1: end-to-end (adapter ingest -> eval -> findings + gap) ────
@pytest.mark.integration
def test_e2e_exactly_covered_findings_fire_and_gap_is_attested(tmp_path):
    from engine import SARoEngine

    manifest = _manifest()
    db = _db()
    summary = builder.build_corpus_to_dir(manifest, tmp_path, seed=42)

    win_s = builder._parse_iso(manifest["window"]["start"])
    win_e = builder._parse_iso(manifest["window"]["end"])
    store = LocalLogStore(tmp_path)
    keys = discover_object_keys(
        store,
        account_id=summary.account_id,
        region=summary.region,
        window_start=win_s,
        window_end=win_e,
    )
    corpus = list(iter_backfill_records(store, keys))

    # Audit sink that runs the REAL engine and captures fired domains per requestId.
    engine_obj = SARoEngine(db)
    fired: dict[str, list[str]] = {}

    def submit(_db, submission, _cfg, envelope):
        engine_obj._sample_findings = []
        engine_obj.run_output_audit(
            audit_id=uuid.uuid5(uuid.NAMESPACE_URL, envelope.request_id),
            raw_output=submission.raw_output,
            prompt=submission.prompt,
            source_model=submission.source_model,
        )
        fired[envelope.request_id] = sorted(
            {f["domain"] for f in engine_obj._sample_findings}
        )

    config = BedrockAdapterConfig(
        tenant_id=_TENANT, user_id=_USER, vertical="healthcare"
    )
    result = replay_backfill(db, corpus, config, submit=submit)
    assert result.malformed == 0 and result.audit_errors == 0
    assert result.checkpoints_written == summary.record_count

    # Exactly the COVERED planted use cases fire; UC-3/4/5 and all clean fire nothing.
    uc_by_rid = {p.request_id: p for p in summary.planted}
    fired_ucs = {
        uc_by_rid[r].use_case for r, doms in fired.items() if r in uc_by_rid and doms
    }
    assert fired_ucs == {"UC-1", "UC-2", "UC-6"}
    assert fired[
        next(p.request_id for p in summary.planted if p.use_case == "UC-1")
    ] == ["Privacy & Security"]
    assert fired[
        next(p.request_id for p in summary.planted if p.use_case == "UC-2")
    ] == ["Misinformation"]
    assert fired[
        next(p.request_id for p in summary.planted if p.use_case == "UC-6")
    ] == ["AI System Safety"]
    # Planted-pending-rule use cases are present in the corpus but fire nothing.
    for uc in ("UC-3", "UC-4", "UC-5"):
        rid = next(p.request_id for p in summary.planted if p.use_case == uc)
        assert fired[rid] == []
    # Clean traffic produces zero findings.
    clean_rids = [r for r in fired if r not in uc_by_rid]
    assert clean_rids and all(fired[r] == [] for r in clean_rids)
    # Total records with a finding == the number of covered planted UCs.
    assert sum(1 for doms in fired.values() if doms) == 3

    # AC-5.1: the deliberate gap surfaces in the coverage attestation. Coverage is keyed
    # by modelId (the primary production model carries the continuous stream).
    primary_model = manifest["primary_model_id"]
    gaps = cov.reconcile_backfill_gaps(
        db,
        tenant_id=_TENANT,
        system_id=primary_model,
        adapter_id="bedrock-invocation-log",
        window_start=win_s,
        window_end=win_e,
        cadence_seconds=int(manifest["cadence_seconds"]),
    )
    assert len(gaps) == 1
    # The reported inter-observation gap CONTAINS the declared missing hour. (It is wider
    # because heartbeats sit at the top of each hour and gap_start anchors at the last
    # observation — consistent with the live detect_gaps semantics.)
    gap_decl_start = builder._parse_iso(manifest["observation_gap"]["start"])
    gap_decl_end = builder._parse_iso(manifest["observation_gap"]["end"])
    g = gaps[0]
    assert cov._aware(g.gap_start) <= gap_decl_start
    assert cov._aware(g.gap_end) >= gap_decl_end

    report = cov.coverage_report(db, _TENANT, primary_model, win_s, win_e)
    assert report["coverage_attested"] is True
    assert len(report["gaps"]) == 1
    assert 0.0 < report["coverage_pct"] < 100.0  # a real, non-vacuous gap was recorded
    db.close()


# ── Security review fixes (path traversal / decompression bomb / manifest injection) ─
@pytest.mark.unit
def test_local_store_rejects_path_traversal_key(tmp_path):
    """A key with a '..' segment must never escape the store root, regardless of shape."""
    secret = tmp_path.parent / "outside-secret.txt"
    secret.write_text("should never be readable via the store")
    store = LocalLogStore(tmp_path)
    with pytest.raises(ValueError):
        store.read_bytes("../outside-secret.txt")
    with pytest.raises(ValueError):
        store.read_bytes(
            "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/"
            "../../../../outside-secret.txt"
        )


@pytest.mark.unit
def test_local_store_rejects_malformed_key_shape(tmp_path):
    """Any key that doesn't match the Bedrock layout is refused before a path is built."""
    store = LocalLogStore(tmp_path)
    for bad in [
        "not-a-key.json.gz",
        "AWSLogs/abc/BedrockModelInvocationLogs/x/1.json.gz",
    ]:
        with pytest.raises(ValueError):
            store.read_bytes(bad)


@pytest.mark.unit
def test_local_store_enforces_object_size_cap(tmp_path, monkeypatch):
    """An oversized object is rejected without being fully materialized in memory."""
    from adapters.bedrock import source as src

    monkeypatch.setattr(src, "MAX_OBJECT_BYTES", 100)
    key = (
        "AWSLogs/999888777666/BedrockModelInvocationLogs/us-east-1/"
        "2026/07/06/00/000000_000.json.gz"
    )
    path = tmp_path / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 1000)
    store = LocalLogStore(tmp_path)
    with pytest.raises(ValueError, match="cap"):
        store.read_bytes(key)


@pytest.mark.unit
def test_bounded_gunzip_rejects_decompression_bomb(monkeypatch):
    """A gzip object whose DECOMPRESSED size exceeds the cap is rejected, not fully expanded."""
    import gzip as gzip_mod

    from adapters.bedrock import source as src

    monkeypatch.setattr(src, "MAX_DECOMPRESSED_BYTES", 1000)
    huge = gzip_mod.compress(b"0" * 5000)
    with pytest.raises(ValueError, match="cap"):
        src._bounded_gunzip(huge)


@pytest.mark.unit
def test_bounded_gunzip_roundtrips_normal_payload():
    import gzip as gzip_mod

    from adapters.bedrock import source as src

    payload = b'{"hello": "world"}\n'
    assert src._bounded_gunzip(gzip_mod.compress(payload)) == payload


@pytest.mark.unit
def test_manifest_account_id_and_region_are_validated():
    """A manifest with a malformed account_id/region is rejected before any path is built
    (guards against path injection via --manifest pointing at an untrusted file)."""
    manifest = _manifest()
    bad = dict(manifest, account_id="../../etc")
    with pytest.raises(ValueError):
        builder.generate_corpus(bad, seed=42)
    bad = dict(manifest, region="us-east-1/../../evil")
    with pytest.raises(ValueError):
        builder.generate_corpus(bad, seed=42)


@pytest.mark.unit
def test_reconcile_backfill_gaps_is_deterministic_on_tied_timestamps():
    """FND (code review): two checkpoints sharing the same watermark_timestamp must
    reconcile in a stable, deterministic order regardless of DB row-return order —
    ordering must not silently depend on insertion order (SQLite happens to preserve
    it; Postgres does not without an explicit secondary key)."""
    from datetime import datetime, timedelta, timezone

    db = _db()
    tenant = uuid.uuid4()
    tied_ts = datetime(2026, 7, 6, 2, 0, tzinfo=timezone.utc)
    # Two checkpoints at the IDENTICAL timestamp, positions in reverse alpha order.
    cov.record_checkpoint(
        db,
        tenant_id=tenant,
        system_id="m",
        adapter_id="bedrock-invocation-log",
        watermark_position="s3:obj:L9",
        watermark_timestamp=tied_ts,
    )
    cov.record_checkpoint(
        db,
        tenant_id=tenant,
        system_id="m",
        adapter_id="bedrock-invocation-log",
        watermark_position="s3:obj:L1",
        watermark_timestamp=tied_ts,
    )
    # A later checkpoint far past cadence, forcing a real gap after the tied pair.
    late_ts = tied_ts + timedelta(hours=5)
    cov.record_checkpoint(
        db,
        tenant_id=tenant,
        system_id="m",
        adapter_id="bedrock-invocation-log",
        watermark_position="s3:obj:L99",
        watermark_timestamp=late_ts,
    )
    gaps1 = cov.reconcile_backfill_gaps(
        db,
        tenant_id=tenant,
        system_id="m",
        adapter_id="bedrock-invocation-log",
        window_start=tied_ts - timedelta(hours=1),
        window_end=late_ts + timedelta(hours=1),
        cadence_seconds=3600,
    )
    assert len(gaps1) == 1
    # Deterministic tiebreak: sorting ties by watermark_position ascending puts L1
    # before L9, so L9 (the higher position) is adjacent to the real gap and becomes
    # its watermark_start — a fixed outcome regardless of which tied row the DB
    # happened to return first (insertion order here is L9 THEN L1, the reverse).
    assert gaps1[0].watermark_start == "s3:obj:L9"
    db.close()
