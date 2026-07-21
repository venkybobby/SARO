#!/usr/bin/env python3
"""Generate the adapter conformance report artifact (STORY-361 AC-3).

Runs the shared scenario suite against every registered adapter and writes a
per-adapter pass/fail matrix as JSON + Markdown. CI uploads both, so "supports
Azure/Vertex" is answerable with an artifact rather than an assertion.

The Markdown output is also the honest input to the buyer-facing capability
matrix (STORY-362): coverage gaps render as gaps, never as ticks.

Usage:
    python scripts/generate_conformance_report.py            # write artifacts
    python scripts/generate_conformance_report.py --check    # fail on any failure
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conformance.harness import run_conformance  # noqa: E402
from conformance.providers import REGISTERED_ADAPTERS  # noqa: E402

OUT_DIR = ROOT / "quality" / "conformance"
JSON_OUT = OUT_DIR / "adapter-conformance.json"
MD_OUT = OUT_DIR / "adapter-conformance.md"


def main(argv: list[str]) -> int:
    report = run_conformance(REGISTERED_ADAPTERS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    MD_OUT.write_text(report.to_markdown(), encoding="utf-8")

    summary = report.to_dict()["summary"]
    scenarios_each = len(report.results) // max(summary["adapters"], 1)
    print(
        f"conformance: {summary['adapters']} adapters x {scenarios_each} scenarios "
        f"= {summary['checks']} checks · {summary['failed']} failed · "
        f"{summary['coverage_gaps']} declared coverage gaps"
    )
    for gap in report.gaps:
        print(f"  gap: {gap.display_name} / {gap.scenario.value} — {gap.reason[:80]}")

    if report.failures:
        print("\nFAILURES:")
        for f in report.failures:
            print(f"  {f.display_name} / {f.scenario.value}: {f.detail}")
        return 1

    if "--check" in argv:
        print("conformance check OK")
    else:
        print(f"wrote {JSON_OUT.relative_to(ROOT)} and {MD_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
