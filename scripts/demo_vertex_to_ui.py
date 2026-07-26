#!/usr/bin/env python3
"""Vertex AI log → adapter → evaluate → DB → persona UI (the full E2E demo).

This is the end-to-end the demo kit was missing: it takes a REAL Vertex export
(the Cloud Logging sink output in a customer-owned GCS bucket, or a downloaded
NDJSON file), runs it through the exact adapter + observation rule packs SARO
uses, and PERSISTS the findings into the evidence tables the UI reads — so the
three personas review and act on them in the running app.

Flow (each step is a real SARO component, nothing mocked):

    1. FETCH    VertexExportReader.for_tenant(...).read_all()   (read-only, INV-6)
                 gs://bucket/prefix   OR   a local export root
    2. PROCESS  adapters/vertex_ai/parse.py -> NormalizedInvocationRecord (body-free)
    3. EVALUATE rule_packs/observation/evaluate.py -> Finding[]
    4. STORE    services/observation_ingest.persist_observation_findings(...)
                 -> Audit + ScanReport + AuditTrace (hash-chained, check_type="observation")
    5. REVIEW   the printed audit_id opens in TRACE View / Risk Register /
                 Compliance Hub for each persona (see docs Part 7).

Usage (local downloaded export — the supported path today):
    python scripts/demo_vertex_to_ui.py --tenant <TENANT_UUID> \\
        --system gemini-prod --source ./vertex-export --container logs \\
        --prefix demo-tenant/ --allowed-tool lookup_care_pathway

    # Download the GCS export objects first, e.g.:
    #   gcloud storage cp -r gs://saro-vertex-export-veriaegis ./vertex-export
    # A direct gs:// source is not yet wired (no GCS ObjectStore backend) and
    # exits with a clear message pointing here.

Tenancy is operator-supplied (--tenant), never read from the log (INV-3). The
allowed-tools policy (--allowed-tool, repeatable) is tenant configuration for
the tool-scope rule pack.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adapters.vertex_ai.source import for_tenant  # noqa: E402
from rule_packs.observation.loader import load_genesis_packs  # noqa: E402
from services.observation_ingest import (  # noqa: E402
    DISCLAIMER,
    persist_observation_findings,
)


def _packs(allowed_tools: list[str]):
    packs = load_genesis_packs()
    out = []
    for ref in sorted(packs):
        p = packs[ref]
        if p.name == "RP-TOOL-SCOPE":
            p = p.with_allowed_tools(allowed_tools)
        out.append(p)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--tenant",
        required=True,
        help="SARO tenant UUID (operator config, not from the log)",
    )
    ap.add_argument(
        "--system", required=True, help="system id, e.g. gemini-prod (labels the audit)"
    )
    ap.add_argument(
        "--source", required=True, help="gs://bucket  OR  a local export root directory"
    )
    ap.add_argument(
        "--container",
        required=True,
        help="bucket/container name the reader is scoped to",
    )
    ap.add_argument("--prefix", default="", help="tenant object prefix (scope guard)")
    ap.add_argument(
        "--allowed-tool",
        action="append",
        default=[],
        dest="allowed_tools",
        help="tenant-allowed tool name for RP-TOOL-SCOPE (repeatable)",
    )
    ap.add_argument(
        "--batch-id", default=None, help="idempotency key (default obs:<system>)"
    )
    args = ap.parse_args(argv)

    try:
        tenant_id = uuid.UUID(args.tenant)
    except ValueError:
        print(f"--tenant must be a UUID (got {args.tenant!r})")
        return 2

    # 1. FETCH — the adapter reads the customer-owned export, read-only.
    if args.source.startswith("gs://"):
        # No gs:// ObjectStore backend is wired yet (build_store only builds a
        # LocalExportStore). Rather than crash with an opaque ValueError, tell
        # the operator to download the export locally for now.
        print(
            "gs:// sources are not yet wired (no GCS ObjectStore backend). "
            "Download the export objects locally and pass --source <dir> "
            "--container <subdir> --prefix <prefix>. See runbook Part 7."
        )
        return 2
    reader = for_tenant(tenant_id, args.container, prefix=args.prefix, root=args.source)
    print(
        f"[1/4] fetch    — reading Vertex export from {args.source} (container={args.container})"
    )
    # 2. PROCESS — parse.py normalizes to body-free records.
    records = reader.read_all()
    print(f"[2/4] process  — {len(records)} invocations normalized (body-free, INV-2)")
    if not records:
        print(
            "no records read — check --source/--container/--prefix and that the sink has delivered objects"
        )
        return 1

    # 3+4. EVALUATE + STORE
    packs = _packs(args.allowed_tools)
    print(
        f"[3/4] evaluate — {', '.join(p.pack_ref for p in packs)}; allowed_tools={args.allowed_tools}"
    )
    from database import get_db

    db = next(get_db())
    try:
        result = persist_observation_findings(
            db,
            tenant_id=tenant_id,
            system_id=args.system,
            records=records,
            packs=packs,
            batch_id=args.batch_id,
        )
    finally:
        db.close()

    if result.skipped_duplicate:
        print(
            f"[4/4] store    — batch already ingested (audit_id={result.audit_id}); "
            "pass a new --batch-id to re-ingest"
        )
        return 0

    print(
        f"[4/4] store    — audit_id={result.audit_id}  "
        f"({result.findings_persisted} findings, score={result.overall_score})"
    )
    for rule_id, n in sorted(result.findings_by_rule.items()):
        print(f"                 {rule_id} ×{n}")
    print()
    print("Review in the UI (audit is now in the DB the personas read):")
    print(
        f"  • AI Auditor     → TRACE View → audit {result.audit_id} (observation traces, hash-chained)"
    )
    print(
        "  • Risk Officer   → Risk Register (this system's observation-coverage score)"
    )
    print(
        "  • Compliance Lead→ Compliance Hub (tamper-evident trail includes these traces)"
    )
    print(
        "  Actions: flag/remediate a finding on the Remedy screen; disposition on TRACE."
    )
    print()
    print(f"Disclaimer: {DISCLAIMER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
