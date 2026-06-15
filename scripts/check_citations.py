#!/usr/bin/env python3
"""PT-003: citation-inventory lint.

Two guarantees, both machine-enforced (run in CI and by tests/test_pt003_citations.py):

1. Completeness — every rule-pack ``rule_id`` has an entry in docs/CITATION_INVENTORY.md.
   A new citation cannot ship without being registered and verified.
2. No misattribution — the 50-sample minimum must never be cited as an EU AI Act Art. 10
   or NIST MAP 2.3 *requirement* in the engine's Gate-1 or the batch schemas. (Legitimate
   Gate-4 ART_10/MAP-2.3 obligation mappings in the rule packs are unaffected.)

Exit 0 = clean, exit 1 = violations (printed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "docs" / "CITATION_INVENTORY.md"
RULE_PACKS = ROOT / "rule_packs"

# Files that must not attribute the sample-size floor to a regulatory article.
# Covers the engine, the batch schemas, AND every router — user-facing error bodies
# and endpoint descriptions are an external claims surface too (PT-003 repo-wide AC).
_SAMPLE_THRESHOLD_FILES = [
    ROOT / "engine.py",
    ROOT / "schemas.py",
    *sorted((ROOT / "routers").glob("*.py")),
]
# A forbidden line ties a sample/minimum context to Art. 10 or MAP 2.3 on the same line.
_FORBIDDEN_SAMPLE_CITATION = re.compile(
    r"(sample|minimum|MIN_SAMPLES).{0,80}(EU AI Act Art\.?\s*10|Art\.?\s*10[^_0-9]|NIST MAP 2\.3|MAP 2\.3)"
    r"|(EU AI Act Art\.?\s*10|NIST MAP 2\.3|MAP 2\.3).{0,80}(sample|minimum)",
    re.IGNORECASE,
)
# A disclaimer explicitly *denies* the attribution with a corrective phrase — that is the
# language we want. Requiring the corrective phrase (not a bare "no"/"not") avoids exempting
# a real misattribution that merely happens to contain an unrelated negation.
_DISCLAIMER = re.compile(
    r"set[s]? no|no batch|NOT\b|not a regulatory|internal SARO methodology|internal statistical",
    re.IGNORECASE,
)


def _rule_ids() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for rules in RULE_PACKS.glob("*/v*/rules.yaml"):
        for line in rules.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*-\s*rule_id:\s*(.+?)\s*$", line)
            if m:
                out.append((m.group(1).strip().strip('"\''), str(rules.relative_to(ROOT))))
    return out


def main() -> int:
    violations: list[str] = []

    if not INVENTORY.exists():
        print(f"ERROR: citation inventory missing: {INVENTORY}")
        return 1
    inventory_text = INVENTORY.read_text(encoding="utf-8")

    for rule_id, pack in _rule_ids():
        if rule_id not in inventory_text:
            violations.append(
                f"rule_id '{rule_id}' from {pack} has no entry in docs/CITATION_INVENTORY.md"
            )

    for path in _SAMPLE_THRESHOLD_FILES:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _FORBIDDEN_SAMPLE_CITATION.search(line) and not _DISCLAIMER.search(line):
                violations.append(
                    f"{path.relative_to(ROOT)}:{i} attributes the sample-size floor to a "
                    f"regulatory article (use internal-methodology language): {line.strip()[:100]}"
                )

    if violations:
        print("Citation lint FAILED:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"Citation lint OK: {len(_rule_ids())} rule-pack citations registered; no misattribution.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
