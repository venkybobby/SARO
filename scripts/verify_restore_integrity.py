#!/usr/bin/env python3
"""Post-restore evidence-integrity verification (STORY-370 AC-2/AC-3).

**The distinction this tool exists for.** SARO already has eight hash-chain
verifiers (`services/self_audit.py`, `rule_pack_snapshot_service.py`,
`evf_publication_service.py`, `grc/evidence.py`, …). Every one of them proves a
chain is *internally self-consistent*. None of them can tell you that a restored
chain is the **same chain you had before the incident**.

A truncated chain is still self-consistent. Restore a backup missing the last
400 events and every verifier returns `valid: true` — the remaining links hash
correctly. What you have lost is evidence, and the tooling built to prove
evidence integrity would report that everything is fine.

So verification needs a reference point captured *before* the loss:

    snapshot  →  (backup taken)  →  … incident …  →  restore  →  verify

`snapshot` records each chain family's tip hash and record count into a manifest
stored **off-platform, alongside the backup**. `verify` recomputes and compares.
Tip alone is not enough either — hence count *and* tip:

| Count vs reference | Tip vs reference | Verdict |
|---|---|---|
| equal | equal | ``MATCH`` — the restore is faithful |
| equal | differs | ``TAMPER`` — same number of records, different content |
| lower | any | ``DATA_LOSS`` — records missing; the delta is the measured RPO |
| higher | any | ``AHEAD`` — verification ran after traffic resumed |

Usage:
    python scripts/verify_restore_integrity.py snapshot --out manifest.json
    python scripts/verify_restore_integrity.py verify --reference manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MANIFEST_SCHEMA = "saro.restore-integrity.v1"

MATCH = "MATCH"
AHEAD = "AHEAD"
TAMPER = "TAMPER"
DATA_LOSS = "DATA_LOSS"
MISSING = "MISSING"
_SEVERITY = {MATCH: 0, AHEAD: 1, DATA_LOSS: 2, TAMPER: 3, MISSING: 3}

# Verdicts that fail the run. AHEAD is a procedural error (verification ran after
# traffic resumed) — reported loudly, but it is not itself evidence loss.
FAILING = {TAMPER, DATA_LOSS, MISSING}


@dataclass(frozen=True)
class ChainReading:
    """One chain family's state at a point in time."""

    family: str
    scope: str  # a tenant id, or "global"
    record_count: int
    tip_hash: Optional[str]
    internally_valid: bool
    note: str = ""

    @property
    def key(self) -> str:
        return f"{self.family}:{self.scope}"


@dataclass(frozen=True)
class FamilyComparison:
    key: str
    verdict: str
    detail: str
    records_lost: int = 0


def build_manifest(readings: list[ChainReading], *, label: str = "") -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "captured_at": datetime.now(tz=timezone.utc).isoformat(),
        "label": label,
        "chains": {r.key: asdict(r) for r in sorted(readings, key=lambda x: x.key)},
    }


def compare(reference: dict[str, Any], current: list[ChainReading]) -> dict[str, Any]:
    """Compare a post-restore reading against a pre-incident manifest."""
    if reference.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(
            f"reference manifest schema {reference.get('schema')!r} is not {MANIFEST_SCHEMA!r}"
        )

    ref_chains: dict[str, dict] = reference.get("chains", {})
    current_by_key = {r.key: r for r in current}
    comparisons: list[FamilyComparison] = []

    for key, ref in sorted(ref_chains.items()):
        now = current_by_key.get(key)
        if now is None:
            # A whole family absent after restore is the most severe outcome and
            # the easiest to overlook: nothing fails, there is simply nothing
            # there to fail.
            comparisons.append(
                FamilyComparison(
                    key,
                    MISSING,
                    f"chain absent after restore (had {ref['record_count']} records)",
                    records_lost=int(ref["record_count"]),
                )
            )
            continue

        if not now.internally_valid:
            comparisons.append(
                FamilyComparison(key, TAMPER, "restored chain fails its own hash verification")
            )
            continue

        ref_count = int(ref["record_count"])
        if now.record_count < ref_count:
            lost = ref_count - now.record_count
            comparisons.append(
                FamilyComparison(
                    key,
                    DATA_LOSS,
                    f"{lost} record(s) missing ({ref_count} → {now.record_count}) — "
                    "self-consistent but incomplete",
                    records_lost=lost,
                )
            )
        elif now.record_count > ref_count:
            comparisons.append(
                FamilyComparison(
                    key,
                    AHEAD,
                    f"{now.record_count - ref_count} record(s) beyond the reference — "
                    "verify before resuming traffic",
                )
            )
        elif now.tip_hash != ref.get("tip_hash"):
            comparisons.append(
                FamilyComparison(
                    key, TAMPER, "record count matches but the chain tip differs — content changed"
                )
            )
        else:
            comparisons.append(FamilyComparison(key, MATCH, "tip and count match the reference"))

    # Families present now but absent from the reference are reported, not
    # failed: a chain created after the manifest was captured is expected.
    for key in sorted(set(current_by_key) - set(ref_chains)):
        comparisons.append(
            FamilyComparison(key, AHEAD, "chain not present in the reference manifest")
        )

    overall = MATCH
    for c in comparisons:
        if _SEVERITY[c.verdict] > _SEVERITY[overall]:
            overall = c.verdict

    return {
        "schema": MANIFEST_SCHEMA,
        "verified_at": datetime.now(tz=timezone.utc).isoformat(),
        "reference_captured_at": reference.get("captured_at"),
        "overall": overall,
        "passed": overall not in FAILING,
        "total_records_lost": sum(c.records_lost for c in comparisons),
        "chains": [asdict(c) for c in comparisons],
    }


# ── Database adapters ───────────────────────────────────────────────────────
# Thin on purpose: the logic worth testing is the pure comparison above. These
# wrap SARO's existing verifiers rather than reimplementing chain checking.


def _self_audit_readings(db: Any) -> list[ChainReading]:
    import services.self_audit as sa
    from models import AuditEvent, Tenant

    out: list[ChainReading] = []
    for (tenant_id,) in db.query(Tenant.id).all():
        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.tenant_id == tenant_id, AuditEvent.seq.isnot(None))
            .order_by(AuditEvent.seq.asc())
            .all()
        )
        if not events:
            continue
        result = sa.verify_audit_chain(db, tenant_id)
        out.append(
            ChainReading(
                family="self_audit",
                scope=str(tenant_id),
                record_count=len(events),
                tip_hash=events[-1].event_hash,
                internally_valid=bool(result.get("valid")),
            )
        )
    return out


def _rule_pack_snapshot_readings(db: Any) -> list[ChainReading]:
    import services.rule_pack_snapshot_service as snap
    from models import RulePackSnapshot

    rows = db.query(RulePackSnapshot).order_by(RulePackSnapshot.created_at.asc()).all()
    if not rows:
        return []
    result = snap.verify_chain(db)
    return [
        ChainReading(
            family="rule_pack_snapshots",
            scope="global",
            record_count=len(rows),
            tip_hash=rows[-1].record_hash,
            internally_valid=bool(result.get("valid")),
            note="published rule-pack versions are immutable (INV-7)",
        )
    ]


CHAIN_FAMILIES: tuple[Callable[[Any], list[ChainReading]], ...] = (
    _self_audit_readings,
    _rule_pack_snapshot_readings,
)


def read_all_chains(db: Any) -> list[ChainReading]:
    readings: list[ChainReading] = []
    for reader in CHAIN_FAMILIES:
        readings.extend(reader(db))
    return readings


def _open_session():
    from database import SessionLocal

    return SessionLocal()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SARO post-restore integrity verification")
    sub = parser.add_subparsers(dest="command", required=True)

    snap_p = sub.add_parser("snapshot", help="capture a pre-incident reference manifest")
    snap_p.add_argument("--out", required=True, type=Path)
    snap_p.add_argument("--label", default="", help="e.g. 'nightly-backup 2026-07-21'")

    ver_p = sub.add_parser("verify", help="compare current state against a reference manifest")
    ver_p.add_argument("--reference", required=True, type=Path)
    ver_p.add_argument("--out", type=Path, help="write the comparison report here")

    args = parser.parse_args(argv)
    db = _open_session()
    try:
        readings = read_all_chains(db)
    finally:
        db.close()

    if args.command == "snapshot":
        manifest = build_manifest(readings, label=args.label)
        args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"captured {len(readings)} chain(s) -> {args.out}")
        print(
            "STORE THIS OFF-PLATFORM, alongside the backup — a manifest that "
            "only exists in the database it describes proves nothing."
        )
        return 0

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    report = compare(reference, readings)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"overall: {report['overall']}")
    for chain in report["chains"]:
        if chain["verdict"] != MATCH:
            print(f"  {chain['verdict']}: {chain['key']} — {chain['detail']}")
    if report["total_records_lost"]:
        print(f"  records lost: {report['total_records_lost']} (this is your measured RPO)")

    if not report["passed"]:
        print("\nFAIL — do not resume traffic. Runbook: docs/ops/dr-backup.md §5")
        return 1
    print("PASS — restored chains match the reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
