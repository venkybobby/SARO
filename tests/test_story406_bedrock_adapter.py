"""STORY-406 — Bedrock invocation-log adapter.

Covers:
  AC-1  parse/normalize Converse + InvokeModel bodies
  AC-2  coverage heartbeat is envelope-only, cursor watermark (INV-2, proven)
  AC-3  audit branch resolves S3 bodies; coverage branch never does
  AC-4  idempotent backfill replay (per-cursor)
  AC-5  source_model mapping + enum
  AC-6  adapter product path stays STORY-336 guard-clean
  Edge  truncation flag; empty-output skips audit; malformed record skipped
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.bedrock import (
    build_audit_submission,
    emit_coverage,
    extract_prompt_output,
    map_source_model,
    parse_envelope,
    replay_backfill,
)
from adapters.bedrock.records import BedrockAdapterConfig
from database import Base
from models import Audit, AuditMetadata, ObservationCheckpoint, ScanReport

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine)
Base.metadata.create_all(_engine)

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000fa")
_USER = uuid.UUID("00000000-0000-0000-0000-0000000000fb")
_TS = "2026-07-07T14:03:11Z"


def _config(allowed=frozenset()) -> BedrockAdapterConfig:
    return BedrockAdapterConfig(
        tenant_id=_TENANT,
        user_id=_USER,
        vertical="finance",
        allowed_s3_buckets=allowed,
    )


def _db():
    db = _Session()
    for tbl in (ObservationCheckpoint, ScanReport, AuditMetadata, Audit):
        db.query(tbl).delete()
    db.commit()
    return db


def _converse_record(
    *,
    model="anthropic.claude-3-5-sonnet-20241022-v2:0",
    stop="end_turn",
    output_text="Sure, here is advice.",
):
    return {
        "requestId": "req-converse-1",
        "region": "us-east-1",
        "operation": "Converse",
        "modelId": model,
        "timestamp": _TS,
        "input": {
            "inputTokenCount": 34,
            "inputBodyJson": {
                "system": [{"text": "You are a cautious advisor."}],
                "messages": [
                    {"role": "user", "content": [{"text": "What should I invest in?"}]},
                    {
                        "role": "user",
                        "content": [
                            {
                                "toolResult": {
                                    "content": [{"text": "market is volatile"}]
                                }
                            }
                        ],
                    },
                ],
                "toolConfig": {
                    "tools": [
                        {"toolSpec": {"name": "get_quote"}},
                        {"toolSpec": {"name": "place_order"}},
                    ]
                },
            },
        },
        "output": {
            "outputTokenCount": 12,
            "outputBodyJson": {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"text": output_text},
                            {
                                "toolUse": {
                                    "name": "get_quote",
                                    "input": {"sym": "ACME"},
                                }
                            },
                        ],
                    }
                },
                "stopReason": stop,
            },
        },
    }


def _invoke_record(*, model="amazon.nova-pro-v1:0"):
    return {
        "requestId": "req-invoke-1",
        "region": "eu-west-1",
        "operation": "InvokeModel",
        "modelId": model,
        "timestamp": _TS,
        "input": {
            "inputBodyJson": {
                "system": "Be terse.",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Summarize the filing."}],
                    }
                ],
                "tools": [{"name": "search_docs"}],
            }
        },
        "output": {
            "outputBodyJson": {
                "content": [
                    {"type": "text", "text": "The filing shows growth."},
                    {"type": "tool_use", "name": "search_docs", "input": {}},
                ],
                "stop_reason": "end_turn",
            }
        },
    }


# ── AC-5 source_model mapping ────────────────────────────────────────────────
@pytest.mark.unit
@pytest.mark.parametrize(
    "model,expected",
    [
        ("anthropic.claude-3-5-sonnet-20241022-v2:0", "claude"),
        ("us.anthropic.claude-3-haiku-20240307-v1:0", "claude"),
        ("amazon.nova-pro-v1:0", "bedrock"),
        ("meta.llama3-70b-instruct-v1:0", "bedrock"),
        ("mistral.mistral-large-2407-v1:0", "bedrock"),
        ("", "bedrock"),
    ],
)
def test_map_source_model(model, expected):
    assert map_source_model(model) == expected


@pytest.mark.unit
def test_ingest_enum_includes_bedrock():
    from routers.ingest import _SOURCE_MODELS

    assert "bedrock" in _SOURCE_MODELS.__args__


# ── AC-1 parse/normalize ─────────────────────────────────────────────────────
@pytest.mark.unit
def test_parse_envelope_converse():
    env = parse_envelope(_converse_record(), cursor="s3:key1:L1")
    assert env.model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert env.operation == "Converse"
    assert env.cursor == "s3:key1:L1"
    assert env.timestamp.tzinfo is not None
    assert env.input_token_count == 34


@pytest.mark.unit
def test_extract_converse_prompt_output():
    prompt, raw_output, truncated, meta = extract_prompt_output(_converse_record())
    assert "You are a cautious advisor." in prompt
    assert "What should I invest in?" in prompt
    assert "market is volatile" in prompt  # toolResult text is surfaced
    assert raw_output == "Sure, here is advice."
    assert truncated is False
    assert meta["tool_config"] == ["get_quote", "place_order"]
    assert meta["tool_use"] == ["get_quote"]
    assert meta["stop_reason"] == "end_turn"


@pytest.mark.unit
def test_extract_invoke_model_prompt_output():
    prompt, raw_output, truncated, meta = extract_prompt_output(_invoke_record())
    assert "Be terse." in prompt
    assert "Summarize the filing." in prompt
    assert raw_output == "The filing shows growth."
    assert meta["tool_config"] == ["search_docs"]
    assert meta["tool_use"] == ["search_docs"]


@pytest.mark.unit
def test_truncated_flag_from_max_tokens():
    _, _, truncated, meta = extract_prompt_output(_converse_record(stop="max_tokens"))
    assert truncated is True
    assert meta["truncated"] is True


# ── AC-3 audit branch + S3 resolution ────────────────────────────────────────
@pytest.mark.unit
def test_build_audit_submission_resolves_s3():
    rec = _converse_record()
    body_in = rec["input"].pop("inputBodyJson")
    body_out = rec["output"].pop("outputBodyJson")
    rec["input"]["inputBodyS3Path"] = "s3://bucket/in.json"
    rec["output"]["outputBodyS3Path"] = "s3://bucket/out.json"
    calls = []

    def resolver(path):
        calls.append(path)
        return body_in if "in.json" in path else body_out

    env = parse_envelope(rec, cursor="c1")
    sub = build_audit_submission(
        rec, env, _config(frozenset({"bucket"})), resolve_body=resolver
    )
    assert sub is not None
    assert sub.raw_output == "Sure, here is advice."
    assert sub.source_model == "claude"
    assert sub.vertical == "finance"
    assert sorted(calls) == ["s3://bucket/in.json", "s3://bucket/out.json"]
    # AC-1 metadata contract (camelCase keys the Wave-1 rules read):
    assert sub.metadata["modelId"] == env.model_id
    assert sub.metadata["requestId"] == "req-converse-1"
    assert sub.metadata["toolConfig"] == ["get_quote", "place_order"]
    assert sub.metadata["toolUse"] == ["get_quote"]
    assert sub.metadata["stopReason"] == "end_turn"


@pytest.mark.unit
def test_empty_output_skips_audit():
    rec = _converse_record(output_text="")
    env = parse_envelope(rec, cursor="c1")
    assert build_audit_submission(rec, env, _config()) is None


# ── AC-2 coverage envelope-only + INV-2 ──────────────────────────────────────
@pytest.mark.unit
def test_emit_coverage_uses_cursor_watermark():
    db = _db()
    env = parse_envelope(_converse_record(), cursor="s3:obj-a:L7")
    cp = emit_coverage(db, env, _config())
    assert cp is not None
    assert cp.watermark_position == "s3:obj-a:L7"
    assert cp.system_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert cp.adapter_id == "bedrock-invocation-log"
    db.close()


@pytest.mark.unit
def test_coverage_never_reads_body_inv2():
    """INV-2: a resolver that raises if touched is never called on the coverage
    path — coverage is structurally body-free (emit_coverage takes an Envelope)."""
    db = _db()

    def landmine(_path):
        raise AssertionError("coverage branch must never resolve a body")

    corpus = [("cur-1", _converse_record())]
    result = replay_backfill(
        db,
        corpus,
        _config(),
        do_audit=False,
        do_coverage=True,
        resolve_body=landmine,
    )
    assert result.checkpoints_written == 1
    assert result.coverage_errors == 0
    db.close()


# ── AC-4 idempotent replay ───────────────────────────────────────────────────
@pytest.mark.unit
def test_backfill_idempotent_per_cursor():
    db = _db()
    corpus = [("cur-A", _converse_record()), ("cur-B", _invoke_record())]

    def fake_submit(_db, submission, _config, _env):
        fake_submit.seen.append(submission.source_model)

    fake_submit.seen = []

    r1 = replay_backfill(db, corpus, _config(), submit=fake_submit)
    assert r1.checkpoints_written == 2
    assert r1.checkpoint_duplicates == 0
    assert r1.audits_submitted == 2
    assert fake_submit.seen == ["claude", "bedrock"]

    r2 = replay_backfill(db, corpus, _config(), submit=fake_submit)
    assert r2.checkpoints_written == 0
    assert r2.checkpoint_duplicates == 2  # same cursors → idempotent no-ops
    # AC-4: the audit branch is idempotent too — a re-run re-audits nothing.
    assert r2.audits_submitted == 0
    assert r2.audits_skipped_duplicate == 2
    assert fake_submit.seen == ["claude", "bedrock"]  # unchanged after 2nd pass

    n = db.query(ObservationCheckpoint).count()
    assert n == 2
    db.close()


@pytest.mark.unit
def test_cursor_sanitized_into_evidence():
    """INV-2: an unsafe cursor (free text/PII, over-long) never lands raw in the
    evidence store — it is surrogated by the opaque-token guard."""
    db = _db()
    env = parse_envelope(_converse_record(), cursor="patient john@doe.com note")
    cp = emit_coverage(db, env, _config())
    assert cp.watermark_position.startswith("op_")  # surrogate, not the raw text
    assert "john@doe.com" not in cp.watermark_position
    db.close()


@pytest.mark.unit
def test_emit_coverage_is_structurally_body_free():
    """The INV-2 guarantee is in the type: emit_coverage takes an Envelope, so it
    cannot receive or fetch a body regardless of implementation."""
    import inspect

    params = set(inspect.signature(emit_coverage).parameters)
    assert params == {"db", "envelope", "config", "checkpoint"}
    assert "resolve_body" not in params and "raw" not in params


@pytest.mark.unit
def test_s3_body_denied_when_bucket_not_allowlisted():
    """FND-1: a log-producer-controlled s3Path outside the operator allowlist is
    refused (audit fails soft), while coverage still succeeds."""
    db = _db()
    rec = _converse_record()
    rec["input"].pop("inputBodyJson")
    rec["input"]["inputBodyS3Path"] = "s3://attacker-bucket/secret.json"

    def resolver(_path):
        raise AssertionError("must never fetch a non-allowlisted bucket")

    result = replay_backfill(
        db,
        [("cur-x", rec)],
        _config(allowed=frozenset({"my-logs"})),
        resolve_body=resolver,
    )
    assert result.audit_errors == 1
    assert result.checkpoints_written == 1  # coverage unaffected
    db.close()


@pytest.mark.unit
def test_s3_fetch_failure_fails_soft():
    """Edge: S3 AccessDenied/missing object fails the audit soft; coverage stands."""
    db = _db()
    rec = _converse_record()
    rec["output"].pop("outputBodyJson")
    rec["output"]["outputBodyS3Path"] = "s3://my-logs/out.json"

    def resolver(_path):
        raise RuntimeError("AccessDenied")

    result = replay_backfill(
        db,
        [("cur-y", rec)],
        _config(allowed=frozenset({"my-logs"})),
        resolve_body=resolver,
    )
    assert result.audit_errors == 1
    assert result.checkpoints_written == 1
    db.close()


@pytest.mark.unit
def test_oversized_inline_body_rejected():
    """FND-2: an inline body over the cap is refused before parsing."""
    from adapters.bedrock.records import MAX_INLINE_BODY_CHARS

    rec = _converse_record()
    rec["input"]["inputBodyJson"] = "x" * (MAX_INLINE_BODY_CHARS + 1)
    env = parse_envelope(rec, cursor="c1")
    with pytest.raises(ValueError, match="cap"):
        build_audit_submission(rec, env, _config())


@pytest.mark.unit
def test_malformed_record_skipped_not_aborting():
    db = _db()
    bad = {"operation": "Converse", "modelId": "anthropic.claude-x"}  # no timestamp
    corpus = [("cur-bad", bad), ("cur-good", _converse_record())]
    result = replay_backfill(db, corpus, _config(), submit=lambda *a: None)
    assert result.malformed == 1
    assert result.checkpoints_written == 1  # the good record still processed
    db.close()


# ── AC-6 STORY-336 guard-clean ───────────────────────────────────────────────
@pytest.mark.unit
def test_adapters_in_product_scan_and_clean():
    from grc.guards import external_model as g

    assert "adapters" in g.PRODUCT_PACKAGE_DIRS
    repo = Path(__file__).resolve().parents[1]
    violations = g.scan_paths([repo / "adapters"], repo_root=repo)
    assert violations == [], f"adapter path is not guard-clean: {violations}"


# ── submit_audit_sync plumbing (engine injected) ─────────────────────────────
@pytest.mark.unit
def test_submit_audit_sync_persists_with_fake_engine():
    from services.audit_submission import submit_audit_sync

    class _FakeEngine:
        def __init__(self, db):
            pass

        def run_output_audit(self, **kw):
            return SimpleNamespace(
                status="completed",
                confidence_score=0.91,
                mit_coverage=SimpleNamespace(score=0.5),
                fixed_delta=SimpleNamespace(delta=0.1),
                bayesian_scores=SimpleNamespace(overall=42.0),
                model_dump=lambda mode="json": {"overall": 42.0},
            )

    db = _db()
    audit_id = submit_audit_sync(
        db,
        tenant_id=_TENANT,
        user_id=_USER,
        prompt="p",
        raw_output="o",
        source_model="claude",
        vertical="finance",
        metadata={"tool_use": ["get_quote"]},
        engine_factory=_FakeEngine,
        persist_traces=lambda *a: None,
    )
    audit = db.get(Audit, audit_id)
    assert audit.status == "completed"
    report = db.query(ScanReport).filter_by(audit_id=audit_id).one()
    assert report.overall_risk_score == 42.0
    assert report.report_json["adapter_metadata"] == {"tool_use": ["get_quote"]}
    db.close()
