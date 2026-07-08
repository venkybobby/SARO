"""Backfill replay orchestration for the Bedrock adapter (STORY-406).

Drives a corpus of (cursor, raw_record) pairs through the two branches:

* **coverage** — :func:`emit_coverage` persists a heartbeat from the ENVELOPE
  ONLY. It never receives a body and never calls ``resolve_body`` (INV-2).
* **audit** — builds an engine-ready payload (may resolve S3 bodies) and hands
  it to an injected ``submit`` callable. Fails soft per record.

Both ``submit`` and ``resolve_body`` are injected (defaults wire to the real
service / a lazy boto3 S3 client), so unit tests need neither a DB-bound engine
nor AWS.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from sqlalchemy.orm import Session

from adapters.bedrock.parse import BodyResolver, build_audit_submission, parse_envelope
from adapters.bedrock.records import (
    BEDROCK_ADAPTER_ID,
    MAX_S3_BODY_BYTES,
    AuditSubmission,
    BedrockAdapterConfig,
    Envelope,
)
from services.observation_coverage_service import _safe_ident, record_checkpoint

logger = logging.getLogger(__name__)

# Injected sink for a built audit payload: (db, submission, config, envelope).
AuditSink = Callable[[Session, AuditSubmission, BedrockAdapterConfig, Envelope], Any]
# Injected coverage sink — same shape as record_checkpoint's keyword contract.
CheckpointSink = Callable[..., Any]


@dataclass
class BackfillResult:
    """Tally of a backfill run — the operator-facing summary of the replay."""

    records: int = 0
    checkpoints_written: int = 0
    checkpoint_duplicates: int = 0
    audits_submitted: int = 0
    audits_skipped: int = 0  # no usable prompt/output
    audits_skipped_duplicate: int = 0  # cursor already processed (AC-4 idempotency)
    malformed: int = 0  # unparseable envelope
    audit_errors: int = 0  # body-resolution / submit failures (fail-soft)
    coverage_errors: int = 0


def emit_coverage(
    db: Session,
    envelope: Envelope,
    config: BedrockAdapterConfig,
    *,
    checkpoint: CheckpointSink = record_checkpoint,
) -> Any:
    """Persist an observation heartbeat from the envelope alone (INV-2).

    Uses the monotonic stream ``cursor`` as the watermark position (backfill,
    D2) — NOT a time bucket — so replay is resumable and idempotent per cursor.
    Identifiers pass through the shared opaque-token guard so no free text can
    reach the evidence store.
    """
    system_id = _safe_ident(envelope.model_id, fallback="unknown")
    adapter_id = _safe_ident(config.adapter_id, fallback=BEDROCK_ADAPTER_ID)
    # The cursor is operator/log-derived (may carry an object key). Route it through
    # the same opaque-token guard as the other identifiers so no free text/PII can
    # reach the evidence store, and an over-long key can't overflow the column (INV-2).
    watermark = _safe_ident(envelope.cursor, fallback="unknown")
    return checkpoint(
        db,
        tenant_id=config.tenant_id,
        system_id=system_id,
        adapter_id=adapter_id,
        watermark_position=watermark,
        watermark_timestamp=envelope.timestamp,
    )


def _default_s3_resolver(s3_path: str) -> dict[str, Any]:
    """Fetch and parse an S3-externalized body. Lazy boto3 import (optional dep).

    Reaches AWS S3 object storage only — never a model-inference service. The read
    is size-capped (FND-2): objects over ``MAX_S3_BODY_BYTES`` are rejected before
    they are pulled into memory. Path validation (scheme + bucket allowlist) is
    applied by the caller's guarded wrapper before this runs.
    """
    import boto3  # lazy: optional dependency, only needed for externalized bodies
    from urllib.parse import urlparse

    parsed = urlparse(s3_path)
    bucket, key = parsed.netloc, parsed.path.lstrip("/")
    client = boto3.client("s3")
    head = client.head_object(Bucket=bucket, Key=key)
    size = head.get("ContentLength", 0)
    if size and size > MAX_S3_BODY_BYTES:
        raise ValueError(
            f"S3 body {s3_path!r} is {size} bytes, over the "
            f"{MAX_S3_BODY_BYTES}-byte cap (FND-2)"
        )
    obj = client.get_object(Bucket=bucket, Key=key)
    # Bounded read: never slurp more than the cap even if ContentLength lied.
    return json.loads(obj["Body"].read(MAX_S3_BODY_BYTES + 1)[:MAX_S3_BODY_BYTES])


def _default_submit(
    db: Session,
    submission: AuditSubmission,
    config: BedrockAdapterConfig,
    envelope: Envelope,
) -> Any:
    """Default audit sink — hand the payload to the synchronous audit service."""
    from services.audit_submission import submit_audit_sync

    return submit_audit_sync(
        db,
        tenant_id=config.tenant_id,
        user_id=config.user_id,
        prompt=submission.prompt,
        raw_output=submission.raw_output,
        source_model=submission.source_model,
        vertical=submission.vertical,
        metadata=submission.metadata,
        dataset_name=f"Bedrock:{envelope.model_id}",
    )


def replay_backfill(
    db: Session,
    records: Iterable[tuple[str, dict[str, Any]]],
    config: BedrockAdapterConfig,
    *,
    checkpoint: CheckpointSink = record_checkpoint,
    submit: Optional[AuditSink] = None,
    resolve_body: Optional[BodyResolver] = None,
    do_coverage: bool = True,
    do_audit: bool = True,
) -> BackfillResult:
    """Replay a historical Bedrock log corpus into SARO's evidence streams.

    ``records`` is an iterable of ``(cursor, raw_record)`` — the cursor is the
    positional stream watermark the caller controls (the log does not carry its
    own). Every branch fails soft per record: one bad record never aborts the
    corpus. Returns a :class:`BackfillResult` tally.
    """
    submit = submit or _default_submit
    resolve_body = resolve_body if resolve_body is not None else _default_s3_resolver
    result = BackfillResult()

    for cursor, raw in records:
        result.records += 1
        try:
            envelope = parse_envelope(raw, cursor=cursor)
        except Exception:  # noqa: BLE001 — one malformed record must not abort replay
            result.malformed += 1
            logger.warning("bedrock adapter: skipping malformed record", exc_info=True)
            continue

        duplicate_cursor = False
        if do_coverage:
            try:
                cp = emit_coverage(db, envelope, config, checkpoint=checkpoint)
                if cp is not None:
                    result.checkpoints_written += 1
                else:
                    result.checkpoint_duplicates += 1  # idempotent re-read (AC-4)
                    duplicate_cursor = True
            except Exception:  # noqa: BLE001 — coverage must never break the replay
                result.coverage_errors += 1
                db.rollback()  # keep the shared session clean for the next record
                logger.warning("bedrock adapter: coverage emit failed", exc_info=True)

        if do_audit:
            # AC-4: a cursor whose checkpoint already existed was processed on a
            # prior pass — do NOT re-audit it (that would duplicate Audit/ScanReport
            # rows and re-run the engine). Audit idempotency rides the coverage
            # duplicate signal, so it requires do_coverage (the backfill default).
            if duplicate_cursor:
                result.audits_skipped_duplicate += 1
                continue
            try:
                submission = build_audit_submission(
                    raw, envelope, config, resolve_body=resolve_body
                )
                if submission is None:
                    result.audits_skipped += 1
                else:
                    submit(db, submission, config, envelope)
                    result.audits_submitted += 1
            except Exception:  # noqa: BLE001 — S3/submit failure fails soft (edge case)
                result.audit_errors += 1
                db.rollback()  # keep the shared session clean for the next record
                logger.warning("bedrock adapter: audit submit failed", exc_info=True)

    return result
