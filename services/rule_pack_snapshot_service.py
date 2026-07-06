"""Rule-pack snapshot service — versioned, immutable, hash-chained (STORY-RPV-001).

The live rule tables (eu_ai_act_rules, governance_rules, nist_ai_rmf_controls) are
the *working copy*. Publishing freezes an immutable snapshot: a hash-chained record
of exactly which rows, at which content, were in force at publish time. Historical
attestations pin to a snapshot version + content hash (STORY-RPV-002) so the exact
criteria for any past evaluation are reproducible despite zero payload retention.

Hash discipline is deliberately identical to services.hash_chain_service: canonical
JSON with sorted keys, ``prev_hash`` folded in, SHA-256 hexdigest. We do NOT invent
a new mechanism (per the story's explicit instruction).

Immutability is enforced in two places (mirroring the EVF split, migration 012):
  * here, at the service layer (guard raises SnapshotImmutableError) — unit-testable
    on the SQLite harness that cannot run plpgsql triggers;
  * in migration 028, by a DB trigger rejecting UPDATE/DELETE — defense in depth on
    real Postgres.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import EUAIActRule, GovernanceRule, NISTControl, RulePackSnapshot

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Validation-status vocabulary (migration radar_scan1_validation_status_columns).
STATUS_SME_VALIDATED = "SME_VALIDATED"
STATUS_DRAFT = "DRAFT_UNVALIDATED"
STATUS_LEGACY = "LEGACY_UNREVIEWED"
STATUS_RETIRED = "RETIRED"

# Ordered rule-table registry. ``has_status`` marks tables that carry the
# validation_status column; tables without it (NIST) are treated as LEGACY.
# Each entry: (table_name, model, has_status_column, canonical_field_list).
_RULE_TABLES = [
    (
        "eu_ai_act_rules",
        EUAIActRule,
        True,
        [
            "article_number",
            "title",
            "risk_level",
            "obligations_providers",
            "obligations_users",
            "description",
            "annex_reference",
            "source_url",
        ],
    ),
    (
        "governance_rules",
        GovernanceRule,
        True,
        ["framework_name", "rule_id", "category", "description", "obligations"],
    ),
    (
        "nist_ai_rmf_controls",
        NISTControl,
        False,
        ["function_name", "subcategory_id", "description", "key_actions", "version"],
    ),
]


class SnapshotError(Exception):
    """Base for rule-pack snapshot errors."""


class DraftRowsPresentError(SnapshotError):
    """DRAFT_UNVALIDATED (or NULL-where-column-exists) rows are in publish scope (AC-3)."""

    def __init__(self, blocking: list[dict]):
        self.blocking = blocking
        preview = ", ".join(f"{b['table']}#{b['id']}" for b in blocking[:5])
        super().__init__(
            f"{len(blocking)} unvalidated rule row(s) block publication: {preview}"
            + (" ..." if len(blocking) > 5 else "")
        )


class EmptyPublishError(SnapshotError):
    """Working copy is identical to the latest published snapshot (no empty versions)."""


class InvalidVersionError(SnapshotError):
    """Version is not valid semver or does not strictly exceed the latest published."""


class SnapshotImmutableError(SnapshotError):
    """Attempted to mutate a published snapshot (AC-2)."""


# ── canonical serialization / hashing ──────────────────────────────────────────
def _canonical_row(table: str, fields: list[str], row) -> str:
    """Deterministic serialization of one rule row over a fixed field set.

    Column order is fixed by ``fields``; NULLs render as empty strings; keys are
    sorted; encoding is UTF-8. The row id and table anchor the payload.
    """
    payload = {"__table__": table, "__id__": str(getattr(row, "id", ""))}
    for f in fields:
        payload[f] = "" if getattr(row, f, None) is None else str(getattr(row, f))
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def compute_row_hash(table: str, row) -> str:
    """SHA-256 over the canonical serialization of a single rule row."""
    fields = next(fl for (t, _m, _h, fl) in _RULE_TABLES if t == table)
    return hashlib.sha256(
        _canonical_row(table, fields, row).encode("utf-8")
    ).hexdigest()


def _content_hash(manifest: dict) -> str:
    """SHA-256 over the full manifest of per-row hashes (order-independent)."""
    canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_hash(
    version: str, content_hash: str, counts: dict, prev_hash: Optional[str]
) -> str:
    """Chain hash over the immutable snapshot fields (see hash_chain_service)."""
    payload = {
        "version": version,
        "content_hash": content_hash,
        "framework_counts": json.dumps(counts, sort_keys=True),
        "prev_hash": prev_hash or "GENESIS",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _parse_semver(version: str) -> tuple[int, int, int]:
    m = _SEMVER.match(str(version))
    if not m:
        raise InvalidVersionError(f"'{version}' is not MAJOR.MINOR.PATCH semver")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


# ── classification ─────────────────────────────────────────────────────────────
def _classify(status: Optional[str], has_status: bool) -> str:
    """Map a row to one of: include | include_legacy | exclude | block."""
    if not has_status:
        return "include_legacy"  # NIST — no lifecycle column yet, treated as legacy
    if status == STATUS_SME_VALIDATED:
        return "include"
    if status == STATUS_LEGACY:
        return "include_legacy"
    if status == STATUS_RETIRED:
        return "exclude"
    # DRAFT_UNVALIDATED or NULL (fail-closed)
    return "block"


def _build_manifest(db: Session, include_legacy: bool) -> tuple[dict, dict, list, bool]:
    """Return (manifest, counts, blocking, legacy_included) for the working copy.

    ``manifest`` = {table: {row_id: row_hash}} over the INCLUDED rows only.
    """
    manifest: dict[str, dict[str, str]] = {}
    counts: dict[str, int] = {}
    blocking: list[dict] = []
    legacy_included = False

    for table, model, has_status, _fields in _RULE_TABLES:
        rows = db.query(model).all()
        included: dict[str, str] = {}
        for row in rows:
            status = getattr(row, "validation_status", None) if has_status else None
            verdict = _classify(status, has_status)
            if verdict == "block":
                blocking.append(
                    {"table": table, "id": getattr(row, "id", None), "status": status}
                )
                continue
            if verdict == "exclude":
                continue
            if verdict == "include_legacy":
                if not include_legacy:
                    continue
                legacy_included = True
            included[str(getattr(row, "id"))] = compute_row_hash(table, row)
        manifest[table] = included
        counts[table] = len(included)
    return manifest, counts, blocking, legacy_included


_LEGACY_CAVEAT = (
    "Includes LEGACY_UNREVIEWED (and status-less NIST) rule rows pending SME "
    "validation; these are provisionally frozen and superseded once validated."
)


# ── ordering (follow the hash chain, not timestamps) ────────────────────────────
def _ordered_chain(db: Session) -> list[RulePackSnapshot]:
    """Return snapshots in true chain order by following prev_hash -> record_hash.

    Ordering by created_at is fragile: two snapshots sharing a timestamp would tie
    on a random UUID and could mis-order the chain that verify_chain walks
    (reviewer S2). The cryptographic links are the authoritative order — genesis is
    the row with prev_hash IS NULL, and each successor is the row whose prev_hash
    equals the current record_hash. Falls back to a deterministic created_at sort
    only if the chain is structurally broken (so a break is still surfaced, not hidden).
    """
    snaps = db.query(RulePackSnapshot).all()
    if not snaps:
        return []

    def _fallback() -> list[RulePackSnapshot]:
        return sorted(snaps, key=lambda s: (s.created_at, str(s.id)))

    by_prev: dict[Optional[str], list[RulePackSnapshot]] = {}
    for s in snaps:
        by_prev.setdefault(s.prev_hash, []).append(s)

    genesis = by_prev.get(None, [])
    if len(genesis) != 1:
        return _fallback()  # zero or multiple genesis rows -> broken chain

    ordered: list[RulePackSnapshot] = []
    seen: set[str] = set()
    cur: Optional[RulePackSnapshot] = genesis[0]
    while cur is not None and cur.record_hash not in seen:
        ordered.append(cur)
        seen.add(cur.record_hash)
        nxt = by_prev.get(cur.record_hash, [])
        cur = nxt[0] if len(nxt) == 1 else None

    if len(ordered) != len(snaps):
        return _fallback()  # fork or dangling row -> broken chain
    return ordered


# ── publish ────────────────────────────────────────────────────────────────────
def get_latest_snapshot(db: Session) -> Optional[RulePackSnapshot]:
    chain = _ordered_chain(db)
    return chain[-1] if chain else None


def list_snapshots(db: Session) -> list[RulePackSnapshot]:
    return _ordered_chain(db)


def publish_snapshot(
    db: Session,
    version: Optional[str] = None,
    publisher_user_id=None,
    include_legacy: Optional[bool] = None,
) -> RulePackSnapshot:
    """Freeze the current working copy into an immutable, hash-chained snapshot.

    Raises:
        DraftRowsPresentError — any DRAFT/NULL-status row is in scope (AC-3).
        EmptyPublishError     — content identical to latest snapshot (no empty versions).
        InvalidVersionError   — bad semver or not strictly increasing.
    """
    if include_legacy is None:
        include_legacy = settings.saro_snapshot_include_legacy

    manifest, counts, blocking, legacy_included = _build_manifest(db, include_legacy)
    if blocking:
        raise DraftRowsPresentError(blocking)

    content_hash = _content_hash(manifest)
    latest = get_latest_snapshot(db)
    if latest is not None and latest.content_hash == content_hash:
        raise EmptyPublishError(
            "working copy is identical to the latest published snapshot"
        )

    version = _resolve_version(version, latest)
    prev_hash = latest.record_hash if latest is not None else None
    record_hash = _record_hash(version, content_hash, counts, prev_hash)

    snap = RulePackSnapshot(
        version=version,
        content_hash=content_hash,
        prev_hash=prev_hash,
        record_hash=record_hash,
        snapshot_manifest=manifest,
        framework_counts=counts,
        includes_legacy=legacy_included,
        caveat=_LEGACY_CAVEAT if legacy_included else None,
        publisher_user_id=publisher_user_id,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def _resolve_version(version: Optional[str], latest: Optional[RulePackSnapshot]) -> str:
    if version is None:
        if latest is None:
            return "1.0.0"
        maj, minr, pat = _parse_semver(latest.version)
        return f"{maj}.{minr}.{pat + 1}"
    new = _parse_semver(version)  # raises InvalidVersionError on bad format
    if latest is not None and new <= _parse_semver(latest.version):
        raise InvalidVersionError(
            f"version {version} must strictly exceed latest published {latest.version}"
        )
    return version


# ── mutation guard (AC-2) ───────────────────────────────────────────────────────
def update_snapshot_version(db: Session, snapshot_id, new_version: str):
    """Guarded no-op: published snapshots are immutable. Always raises (AC-2)."""
    raise SnapshotImmutableError(
        f"snapshot {snapshot_id} is immutable — published snapshots cannot be modified"
    )


# ── diff / changelog (AC-4) ─────────────────────────────────────────────────────
def diff_against_latest(db: Session) -> dict:
    """Machine-readable changelog of the working copy vs the latest snapshot.

    Returns {table: {added: [ids], updated: [ids], retired: [ids]}}. A row present
    in the snapshot but absent (deleted or now-excluded) from the working copy is
    reported as retired, never silently dropped.
    """
    latest = get_latest_snapshot(db)
    snapshot_manifest = latest.snapshot_manifest if latest is not None else {}
    # Compare the current *includable* set (what the next publish would freeze) vs
    # the snapshot manifest, so a row flipped to RETIRED/DRAFT drops out and is
    # reported as retired — not silently mislabelled "updated" (reviewer S1).
    include_legacy = settings.saro_snapshot_include_legacy
    current_manifest, _counts, _blocking, _legacy = _build_manifest(db, include_legacy)
    result: dict[str, dict] = {}
    for table, _model, _has, _fields in _RULE_TABLES:
        current = dict(current_manifest.get(table, {}))
        prior = dict(snapshot_manifest.get(table, {}))
        added = sorted(set(current) - set(prior), key=_as_int)
        retired = sorted(set(prior) - set(current), key=_as_int)
        updated = sorted(
            [rid for rid in set(current) & set(prior) if current[rid] != prior[rid]],
            key=_as_int,
        )
        result[table] = {"added": added, "updated": updated, "retired": retired}
    return result


def _as_int(s: str):
    try:
        return (0, int(s))
    except (TypeError, ValueError):
        return (1, str(s))


# ── verify (AC-5) ────────────────────────────────────────────────────────────────
def verify_chain(db: Session) -> dict:
    """Recompute the snapshot chain from genesis; identify any tampered version."""
    snaps = list_snapshots(db)
    prev_hash: Optional[str] = None
    for snap in snaps:
        # Re-derive content_hash from the stored manifest: an out-of-band edit to
        # snapshot_manifest (the per-row rule hashes RPV-002 pins evidence to) that
        # leaves content_hash stale would otherwise pass verification (reviewer B2).
        manifest_hash = _content_hash(snap.snapshot_manifest)
        expected = _record_hash(
            snap.version, snap.content_hash, snap.framework_counts, prev_hash
        )
        if (
            manifest_hash != snap.content_hash
            or expected != snap.record_hash
            or snap.prev_hash != prev_hash
        ):
            return {
                "valid": False,
                "versions_checked": snaps.index(snap),
                "break_at_version": snap.version,
                "expected_hash": expected,
                "actual_hash": snap.record_hash,
                "content_hash_mismatch": manifest_hash != snap.content_hash,
            }
        prev_hash = snap.record_hash
    return {
        "valid": True,
        "versions_checked": len(snaps),
        "break_at_version": None,
        "expected_hash": None,
        "actual_hash": None,
    }
