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
def _row_payload(table: str, fields: list[str], row) -> dict:
    """Frozen field dict for one rule row (the reproducible content, STORY-RPV-002).

    NULLs render as empty strings; the table + id anchor the payload so a hash is
    collision-safe across tables.
    """
    payload = {"__table__": table, "__id__": str(getattr(row, "id", ""))}
    for f in fields:
        payload[f] = "" if getattr(row, f, None) is None else str(getattr(row, f))
    return payload


def _canonical_row(table: str, fields: list[str], row) -> str:
    """Deterministic serialization of one rule row over a fixed field set.

    Column order is fixed by ``fields``; NULLs render as empty strings; keys are
    sorted; encoding is UTF-8. The row id and table anchor the payload.
    """
    return json.dumps(
        _row_payload(table, fields, row), sort_keys=True, ensure_ascii=False
    )


def _hash_row_payload(payload: dict) -> str:
    """SHA-256 over a frozen row payload dict (the stored snapshot_content form).

    Lets reproduction re-derive a stored row's hash and cross-check it against the
    manifest, so snapshot_content cannot be tampered independently of the chain.
    """
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def compute_row_hash(table: str, row) -> str:
    """SHA-256 over the canonical serialization of a single rule row."""
    fields = next(fl for (t, _m, _h, fl) in _RULE_TABLES if t == table)
    return _hash_row_payload(_row_payload(table, fields, row))


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


def _build_manifest(
    db: Session, include_legacy: bool
) -> tuple[dict, dict, list, bool, dict]:
    """Return (manifest, counts, blocking, legacy_included, content) for the working copy.

    ``manifest`` = {table: {row_id: row_hash}} over the INCLUDED rows only.
    ``content``  = {table: {row_id: {field: value}}} — the frozen full rows for
    exact criteria reproduction (STORY-RPV-002), same included set as the manifest.
    """
    manifest: dict[str, dict[str, str]] = {}
    content: dict[str, dict[str, dict]] = {}
    counts: dict[str, int] = {}
    blocking: list[dict] = []
    legacy_included = False

    for table, model, has_status, fields in _RULE_TABLES:
        rows = db.query(model).all()
        included: dict[str, str] = {}
        included_content: dict[str, dict] = {}
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
            rid = str(getattr(row, "id"))
            included[rid] = compute_row_hash(table, row)
            included_content[rid] = _row_payload(table, fields, row)
        manifest[table] = included
        content[table] = included_content
        counts[table] = len(included)
    return manifest, counts, blocking, legacy_included, content


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

    manifest, counts, blocking, legacy_included, content = _build_manifest(
        db, include_legacy
    )
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
        snapshot_content=content,
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
    current_manifest, _counts, _blocking, _legacy, _content = _build_manifest(
        db, include_legacy
    )
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


# ── evaluation-time version resolution + criteria reproduction (STORY-RPV-002) ───
MODE_PERMISSIVE = "PERMISSIVE"
MODE_STRICT = "STRICT"

PRE_VERSIONING = "PRE-VERSIONING"


class RulePackResolutionError(SnapshotError):
    """STRICT mode refuses: no published version, or the working copy has drifted."""


class RulePackIntegrityError(SnapshotError):
    """Snapshot chain is broken at pin time — refuse in BOTH modes (incident)."""


def get_snapshot_by_version(db: Session, version: str) -> Optional[RulePackSnapshot]:
    return (
        db.query(RulePackSnapshot).filter(RulePackSnapshot.version == version).first()
    )


def resolve_pinned_version(
    db: Session, mode: Optional[str] = None
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the rule-pack version to pin to an evaluation (AC-2, AC-5).

    Returns (version, content_hash), or (None, None) for PRE-VERSIONING in
    PERMISSIVE mode when nothing is published. Resolution is per invocation; the
    result is derived only from published snapshots, never the working copy.

    Raises:
        RulePackResolutionError — STRICT and (no published version OR working-copy drift).
        RulePackIntegrityError  — the snapshot chain is broken (refused in both modes).
    """
    resolved_mode = (
        mode or settings.saro_rule_pack_eval_mode or MODE_PERMISSIVE
    ).upper()
    latest = get_latest_snapshot(db)
    if latest is None:
        if resolved_mode == MODE_STRICT:
            raise RulePackResolutionError(
                "no published rule-pack version exists (STRICT mode refuses to evaluate)"
            )
        return None, None  # PERMISSIVE: pre-versioning, evaluation proceeds unpinned

    # Integrity gate at pin time — a broken chain is an incident, not a warning.
    chain = verify_chain(db)
    if not chain["valid"]:
        raise RulePackIntegrityError(
            f"rule-pack snapshot chain is broken at version {chain['break_at_version']}"
        )

    if resolved_mode == MODE_STRICT:
        diff = diff_against_latest(db)
        drifted = any(
            fr["added"] or fr["updated"] or fr["retired"] for fr in diff.values()
        )
        if drifted:
            raise RulePackResolutionError(
                "working copy has drifted from the latest published version "
                "(STRICT mode refuses; publish a new version or switch to PERMISSIVE)"
            )
    return latest.version, latest.content_hash


def reproduce_criteria(db: Session, version: str) -> dict:
    """Return the full frozen rule content of a pinned version (AC-3).

    Reads snapshot_content (frozen at publish), so reproduction is exact even after
    the working copy mutates. Carries chain-verification status. Snapshots published
    before RPV-002 have no snapshot_content -> reproduction_available is False with a
    stated limitation (never a guess).
    """
    snap = get_snapshot_by_version(db, version)
    if snap is None:
        raise RulePackResolutionError(f"no rule-pack snapshot for version {version}")
    content = snap.snapshot_content or {}
    manifest = snap.snapshot_manifest or {}
    chain = verify_chain(db)

    # Cross-check snapshot_content against the (chain-covered) manifest hashes:
    # snapshot_content itself is not in content_hash, so without this an out-of-band
    # edit to the reproduced rows would go undetected while the chain still verifies
    # (reviewer B2 — same class as FND-039, one layer deeper). Any row whose stored
    # payload does not hash to its manifest entry fails content integrity.
    content_integrity = True
    for table, rows in content.items():
        table_manifest = manifest.get(table, {})
        for rid, payload in rows.items():
            if _hash_row_payload(payload) != table_manifest.get(rid):
                content_integrity = False
                break
        if not content_integrity:
            break

    available = bool(content) and content_integrity
    if not content:
        limitation = (
            "This snapshot predates full-content storage (RPV-001-only); "
            "exact criteria reproduction is unavailable for it."
        )
    elif not content_integrity:
        limitation = (
            "Stored criteria content failed its integrity cross-check against the "
            "hash-chained manifest — reproduction is not trustworthy (possible "
            "out-of-band tampering). Treat as an incident."
        )
    else:
        limitation = None

    return {
        "version": snap.version,
        "content_hash": snap.content_hash,
        "reproduction_available": available,
        "content_integrity": content_integrity,
        "frameworks": {t: list(rows.values()) for t, rows in content.items()},
        "chain_verification": {
            "valid": chain["valid"],
            "break_at_version": chain["break_at_version"],
        },
        "limitation": limitation,
    }
