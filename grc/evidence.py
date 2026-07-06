"""STORY-305 — Append-only, tamper-evident evidence store.

The layer an auditor actually inspects. Every consequential output is persisted
with full provenance so audit conclusions are reproducible. Tamper-evidence is a
hash chain over a deterministic serialization of each record:

    content_hash = SHA256(canonical_payload)
    chain_hash   = SHA256(content_hash + prev_chain_hash)

The genesis record uses an explicit constant ``GENESIS`` for ``prev_chain_hash``.
Append-only is enforced both at the DB layer (trigger, migration 025) and here at
the app layer — this module exposes capture/get/verify only; there is no update
or delete path.

``REQUIRED_PROVENANCE_FIELDS`` is the single source of truth for what "complete
provenance" means; the provenance-completeness gate (STORY-306) imports it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import GRCEvidenceRecord

GENESIS = "GENESIS"

# Provenance fields persisted and hashed. Also the completeness contract (306).
REQUIRED_PROVENANCE_FIELDS = (
    "model_version",
    "prompt",
    "retrieved_context",
    "decision",
    "confidence",
    "consumer",
    "captured_at",
)

# Fields included in the deterministic content hash. UNCHANGED across RPV-002 so
# pre-RPV-002 records verify identically (see _PIN_FIELDS for the additive pin).
_PAYLOAD_FIELDS = (
    "output_id",
    "system_id",
    "model_version",
    "prompt",
    "inputs",
    "retrieved_context",
    "decision",
    "confidence",
    "consumer",
    "captured_at",
)

# STORY-RPV-002: the rule-pack criteria pin. Hashed so it is tamper-evident (an
# examiner can trust the version this attestation was evaluated against), but folded
# in ONLY when present — a NULL pin (pre-RPV-002 record, or a PERMISSIVE unpinned
# capture) serializes exactly as a legacy payload did, so historical content_hashes
# still verify (reviewer B1 / AC-4). Never remove or reorder existing fields.
_PIN_FIELDS = (
    "rule_pack_version_id",
    "rule_pack_content_hash",
)


class EvidenceCapture(BaseModel):
    """Input payload for capturing one evidence record."""

    output_id: str
    system_id: str | None = None
    model_version: str | None = None
    prompt: str | None = None
    inputs: dict[str, Any] | None = None
    retrieved_context: str | None = None
    decision: str | None = None
    confidence: float | None = None
    consumer: str | None = None
    captured_at: datetime | None = None


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        # Normalize to UTC-naive so the hash is stable across DB round-trips
        # (SQLite stores naive; Postgres timestamptz returns aware UTC).
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def canonical_payload(data: dict[str, Any]) -> str:
    """Deterministic (stable key order) JSON serialization of the payload.

    The rule-pack pin fields are appended ONLY when non-NULL, so a record without a
    pin serializes byte-for-byte as it did before RPV-002 — historical content_hashes
    keep verifying (reviewer B1).
    """
    payload = {f: data.get(f) for f in _PAYLOAD_FIELDS}
    for f in _PIN_FIELDS:
        if data.get(f) is not None:
            payload[f] = data.get(f)
    return json.dumps(payload, sort_keys=True, default=_json_default)


def compute_content_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(data).encode("utf-8")).hexdigest()


def compute_chain_hash(content_hash: str, prev_chain_hash: str) -> str:
    return hashlib.sha256((content_hash + prev_chain_hash).encode("utf-8")).hexdigest()


def _chain_tail(db: Session, tenant_id: uuid.UUID) -> tuple[str, int]:
    """Return (last chain_hash, last seq) for a tenant, or (GENESIS, 0)."""
    q = (
        db.query(GRCEvidenceRecord.chain_hash, GRCEvidenceRecord.seq)
        .filter(GRCEvidenceRecord.tenant_id == tenant_id)
        .order_by(GRCEvidenceRecord.seq.desc())
    )
    # Serialize concurrent writers on the tenant's chain tail (Postgres). SQLite
    # ignores FOR UPDATE; the unique (tenant_id, seq) index is the backstop there.
    row = q.with_for_update().first()
    return (row[0], row[1]) if row else (GENESIS, 0)


def capture_evidence(
    db: Session, *, tenant_id: uuid.UUID, capture: EvidenceCapture
) -> GRCEvidenceRecord:
    """Persist one evidence record, chained to its tenant's predecessor.

    A per-tenant ``seq`` gives a deterministic chain order independent of
    timestamp resolution. On Postgres a row lock on the tenant's tail serializes
    concurrent writers so the chain cannot fork (no-op on SQLite tests).
    """
    data = capture.model_dump()
    if data.get("captured_at") is None:
        data["captured_at"] = datetime.now(tz=timezone.utc)

    # STORY-RPV-002 (AC-1/AC-2/AC-5): resolve the rule-pack version in force and pin
    # it onto the record (inside the content hash). Resolution is per invocation and
    # derives only from published snapshots, never the working copy. STRICT mode may
    # refuse here (no published version / working-copy drift) or raise on a broken
    # chain — both propagate so an unpinnable evaluation is not silently persisted.
    from services.rule_pack_snapshot_service import resolve_pinned_version

    version_id, version_hash = resolve_pinned_version(db)
    data["rule_pack_version_id"] = version_id
    data["rule_pack_content_hash"] = version_hash

    content_hash = compute_content_hash(data)
    prev_chain_hash, last_seq = _chain_tail(db, tenant_id)
    chain_hash = compute_chain_hash(content_hash, prev_chain_hash)

    record = GRCEvidenceRecord(
        tenant_id=tenant_id,
        seq=last_seq + 1,
        content_hash=content_hash,
        prev_chain_hash=prev_chain_hash,
        chain_hash=chain_hash,
        **data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_evidence(
    db: Session, *, tenant_id: uuid.UUID, evidence_id: uuid.UUID
) -> GRCEvidenceRecord | None:
    return (
        db.query(GRCEvidenceRecord)
        .filter(
            GRCEvidenceRecord.id == evidence_id,
            GRCEvidenceRecord.tenant_id == tenant_id,
        )
        .first()
    )


def _record_to_payload(record: GRCEvidenceRecord) -> dict[str, Any]:
    data = {f: getattr(record, f) for f in _PAYLOAD_FIELDS}
    # Surface the pin so canonical_payload folds it in when present; absent/NULL
    # pins are skipped by canonical_payload, preserving legacy verification.
    for f in _PIN_FIELDS:
        data[f] = getattr(record, f, None)
    return data


class ChainVerification(BaseModel):
    valid: bool
    records_checked: int
    first_broken_id: str | None = None
    reason: str | None = None


def verify_chain(records: list[GRCEvidenceRecord]) -> ChainVerification:
    """Walk an ordered chain; report the first broken link, if any.

    Records must be supplied in insertion order. Each record's recomputed
    content hash must match, its ``prev_chain_hash`` must equal the running
    chain value, and its ``chain_hash`` must equal SHA256(content+prev).
    """
    prev = GENESIS
    for i, rec in enumerate(records):
        expected_content = compute_content_hash(_record_to_payload(rec))
        if rec.content_hash != expected_content:
            return ChainVerification(
                valid=False,
                records_checked=i + 1,
                first_broken_id=str(rec.id),
                reason="content_hash mismatch (payload mutated)",
            )
        if rec.prev_chain_hash != prev:
            return ChainVerification(
                valid=False,
                records_checked=i + 1,
                first_broken_id=str(rec.id),
                reason="prev_chain_hash does not match predecessor",
            )
        expected_chain = compute_chain_hash(rec.content_hash, rec.prev_chain_hash)
        if rec.chain_hash != expected_chain:
            return ChainVerification(
                valid=False,
                records_checked=i + 1,
                first_broken_id=str(rec.id),
                reason="chain_hash mismatch",
            )
        prev = rec.chain_hash
    return ChainVerification(valid=True, records_checked=len(records))


def verify_tenant_chain(db: Session, *, tenant_id: uuid.UUID) -> ChainVerification:
    """Load a tenant's full evidence chain in order and verify it."""
    records = (
        db.query(GRCEvidenceRecord)
        .filter(GRCEvidenceRecord.tenant_id == tenant_id)
        .order_by(GRCEvidenceRecord.seq.asc())
        .all()
    )
    return verify_chain(records)
