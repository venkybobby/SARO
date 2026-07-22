#!/usr/bin/env python3
"""Buyer-facing validation report generator (STORY-379).

A technical buyer asks "what are your false-positive and false-negative rates?"
This turns the confusion-matrix artifact (STORY-378) into a report they can take
to their own risk review — **markdown + PDF, every number read from the
artifact, none hand-typed** (AC-1). Generation is the anti-drift mechanism: the
report cannot claim a rate the harness did not measure.

Two honesty constraints are enforced in the generator, not left to the author:

* **Limitations are derived from the actual state**, not written optimistically.
  Which tiers were measured, whether the completion bar is signed, how many packs
  and adapters — all read from the artifact and the bar. If only T1 is covered,
  the report says so prominently; it does not imply broader validation.

* **Language guardrails** (docs/compliance-claims.md): the generator refuses to
  emit "certified", "compliant", client results, or any prohibited claim phrase.
  A report that overclaims is worse than none.

Usage:
    python scripts/generate_validation_report.py           # write md + pdf
    python scripts/generate_validation_report.py --check   # fail if stale/forbidden
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MATRIX = ROOT / "quality" / "validation" / "confusion-latest.json"
OUT_DIR = ROOT / "docs" / "validation"
MD_OUT = OUT_DIR / "validation-report.md"
PDF_OUT = OUT_DIR / "validation-report.pdf"

# Same closed list as the capability-matrix generator — a claim a compliance
# tool must never make about itself.
PROHIBITED_PHRASES = (
    "certified",
    "certification",
    "compliant",
    "guarantees compliance",
    "regulatory approval",
    "conformity assessment",
)

ALL_TIERS = {
    "T1": "synthetic-deterministic",
    "T2": "synthetic-adversarial",
    "T3": "offline labeled",
    "T4": "pilot labeled",
}


def _load_matrix() -> dict[str, Any]:
    if not MATRIX.exists():
        raise FileNotFoundError(
            f"{MATRIX} not found — run scripts/confusion_matrix_harness.py first"
        )
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def _fmt(value: Any) -> str:
    return "-" if value is None else str(value)


def build_markdown() -> str:
    m = _load_matrix()
    import services.validation_bar as validation_bar

    bar = validation_bar.proposal_summary()
    tier = m.get("tier", "?")
    covered = {tier}

    lines: list[str] = [
        "# SARO Rule-Pack Validation Report",
        "",
        "> **Generated** by `scripts/generate_validation_report.py` from the "
        "confusion-matrix artifact (STORY-378). Every rate below is measured, "
        "not asserted — regenerating this report cannot state a number the "
        "harness did not produce.",
        "",
        f"- **Generated:** {datetime.now(tz=timezone.utc).date().isoformat()}",
        f"- **Corpus tier measured:** {tier} ({ALL_TIERS.get(tier, 'unknown')})",
        f"- **Corpus records:** {m.get('corpus_records', '?')}",
        f"- **Completion bar:** {bar['status']}"
        + ("" if bar["in_force"] else " - **not yet signed** (see Limitations)"),
        "",
        "## What this measures",
        "",
        "For each rule-pack, the rate at which its rules fire when they should "
        "(recall) and fire only when they should (precision), measured against a "
        "labeled corpus. These are **analytical measurements of SARO's own rule "
        "behaviour** - they are not a determination about any customer system, and "
        "SARO does not issue verdicts.",
        "",
        "## Results",
        "",
        "| Rule pack | Precision | Recall | F1 | TP | FP | FN | TN |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for ref, pack in sorted(m["packs"].items()):
        o = pack["overall"]
        lines.append(
            f"| {ref} | {_fmt(o['precision'])} | {_fmt(o['recall'])} | "
            f"{_fmt(o['f1'])} | {o['tp']} | {o['fp']} | {o['fn']} | {o['tn']} |"
        )

    lines += ["", "### Per-rule detail", ""]
    for ref, pack in sorted(m["packs"].items()):
        lines += [
            f"**{ref}**",
            "",
            "| Rule | Precision | Recall | TP | FP | FN | TN |",
            "|---|---|---|---|---|---|---|",
        ]
        for rule_id, c in sorted(pack["rules"].items()):
            lines.append(
                f"| {rule_id} | {_fmt(c['precision'])} | {_fmt(c['recall'])} | "
                f"{c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} |"
            )
        lines.append("")

    uncovered = [f"{t} ({ALL_TIERS[t]})" for t in ("T1", "T2", "T3", "T4") if t not in covered]
    lines += [
        "## Limitations - read this before relying on the numbers above",
        "",
        "Understatement over overstatement. These results are real but narrow:",
        "",
        f"- **Only tier {tier} was measured.** Tiers not yet covered: "
        + ", ".join(uncovered)
        + ". A perfect score on a synthetic tier does not demonstrate behaviour "
        "on adversarial or real-world data.",
        "- **The corpus is synthetic.** It is deterministic and labeled by "
        "construction, which makes it reproducible - but it is not real customer "
        "traffic. Real-world (T3) and pilot (T4) data are how these rates are "
        "validated against reality, and that data is not yet in place.",
        f"- **{len(m['packs'])} rule-pack(s)** were measured: "
        + ", ".join(sorted(m["packs"]))
        + ". Other packs are not covered by this report.",
    ]
    if not bar["in_force"]:
        lines += [
            "- **No completion bar is signed yet.** The pass/fail thresholds "
            "(STORY-377) are proposed and awaiting owner sign-off. Until then "
            "these are *measured rates*, not a pass against an agreed bar - this "
            "report describes behaviour, it does not validate it against a target.",
        ]
    lines += [
        "- **Adapters not yet validated on real data:** the observation adapters "
        "(Azure OpenAI, Vertex AI) are exercised by the conformance suite but "
        "their FP/FN rates on real provider logs are not yet measured.",
        "",
        "## How these numbers were produced",
        "",
        "The rule engine is deterministic and makes no external model calls "
        "(INV-1). The labeled corpus is built by `scripts/build_validation_corpus.py` "
        "and verified byte-identical in CI, so the confusion matrix is reproducible "
        "run to run. This report is regenerated from that artifact; it contains no "
        "hand-entered figures.",
        "",
        "---",
        "",
        "*This is a report of SARO's own rule-pack measurements for a technical "
        "reviewer. It carries no regulatory weight, is not a determination under "
        "any framework, and includes no customer results. Human review by "
        "qualified personnel is required before any regulatory submission.*",
        "",
    ]
    return "\n".join(lines) + "\n"


def _check_language(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in PROHIBITED_PHRASES if p in lowered]


def build_pdf(markdown: str) -> bytes:
    from fpdf import FPDF, XPos, YPos

    def _ascii(s: str) -> str:
        return s.encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_left_margin(18)
    pdf.set_right_margin(18)
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(0, 9, _ascii(line[2:]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, _ascii(line[3:]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 6, _ascii(line[4:]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line.startswith("|"):
            pdf.set_font("Courier", "", 8)
            pdf.multi_cell(0, 4.5, _ascii(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5.5, _ascii(line.lstrip("> ").lstrip("- ")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.ln(2)
    return bytes(pdf.output())


def main(argv: list[str]) -> int:
    md = build_markdown()

    violations = _check_language(md)
    if violations:
        print(f"FAIL: prohibited claim language in the validation report: {violations}")
        print("See docs/compliance-claims.md - SARO reports measurements, not verdicts.")
        return 1

    if "--check" in argv:
        if not MD_OUT.exists() or MD_OUT.read_text(encoding="utf-8") != md:
            print("FAIL: docs/validation/validation-report.md is stale - regenerate it")
            return 1
        print("validation report OK: matches the confusion-matrix artifact")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MD_OUT.write_text(md, encoding="utf-8")
    PDF_OUT.write_bytes(build_pdf(md))
    print(f"wrote {MD_OUT.relative_to(ROOT)} and {PDF_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
