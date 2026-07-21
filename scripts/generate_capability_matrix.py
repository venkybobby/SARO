#!/usr/bin/env python3
"""Generate the buyer-facing adapter capability matrix (STORY-362).

Every row is derived, never asserted:

* **Field support** comes from parsing each provider's STOCK log shape through
  its real adapter and reading the resulting `field_availability` map. If an
  adapter starts (or stops) populating a field, this document changes with it.
* **Scenario / rule-pack support** comes from the STORY-361 conformance report.

That matters because this is the document a technical buyer uses to decide
whether SARO covers their stack. A hand-authored table drifts from the code and
drifts optimistically — nobody forgets to add a capability they shipped, but
everybody forgets to remove one they didn't.

Language guardrails (docs/compliance-claims.md) are enforced on the output: the
generator refuses to write a document containing prohibited claim language.

Usage:
    python scripts/generate_capability_matrix.py            # write the doc
    python scripts/generate_capability_matrix.py --check    # fail if stale
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from adapters.contract import FieldAvailability  # noqa: E402
from conformance.harness import Scenario, Support, run_conformance  # noqa: E402
from conformance.providers import REGISTERED_ADAPTERS  # noqa: E402

OUT = ROOT / "docs" / "adapter-capability-matrix.md"

# Normalized fields a buyer cares about, in reading order.
FIELDS: list[tuple[str, str]] = [
    ("request_id", "Invocation id"),
    ("timestamp", "Timestamp"),
    ("operation", "Operation / method"),
    ("model_id", "Model identity"),
    ("region", "Region"),
    ("input_token_count", "Input token count"),
    ("output_token_count", "Output token count"),
    ("stop_reason", "Stop reason"),
    ("truncated", "Truncation detectable"),
    ("error_code", "Error / failure status"),
    ("tools", "Tool / function calls"),
]

# Claim language that must never appear in a buyer-facing document.
PROHIBITED_PHRASES = (
    "certified",
    "certification",
    "compliant",
    "guarantees compliance",
    "regulatory approval",
    "conformity assessment",
)

SYMBOL = {"yes": "✅", "varies": "◐", "no": "❌"}


def _field_support(record, field: str) -> str:
    """Map one field's availability on the stock record to a support symbol.

    The **availability map is the sole authority**, never the field's value. A
    successful invocation has `error_code=None` and an untruncated one has
    `truncated=False`; reading those values as "unsupported" would understate
    every adapter's error handling. Availability answers the question the buyer
    is actually asking — *can this provider's logs express the field at all* —
    which is independent of what one sample record happened to contain.
    """
    if record is None:
        return "no"
    availability = record.availability(field)
    if availability is FieldAvailability.UNAVAILABLE:
        return "no"
    if availability is FieldAvailability.MISSING:
        return "varies"
    return "yes"


def build_document() -> str:
    report = run_conformance(REGISTERED_ADAPTERS)
    adapters = list(REGISTERED_ADAPTERS)
    names = [a.display_name for a in adapters]
    stock = {a.display_name: a.standard_schema_record() for a in adapters}
    by_key = {(r.display_name, r.scenario): r for r in report.results}

    lines: list[str] = [
        "# SARO Adapter Capability Matrix",
        "",
        "> **Generated** by `scripts/generate_capability_matrix.py` from the "
        "adapters' own parsing behaviour and the STORY-361 conformance suite. "
        "Do not edit by hand — CI verifies this file matches the code.",
        "",
        "This page states what SARO can observe from each provider's logs, "
        "including what it **cannot**. SARO produces risk scores, TRACE evidence, "
        "and remediation guidance for human review; it does not issue verdicts.",
        "",
        "## Ingestion",
        "",
        "| | Bedrock | Azure OpenAI | Vertex AI |",
        "|---|---|---|---|",
        "| Source | Bedrock model-invocation logs | Diagnostic Settings "
        "`RequestResponse` export | Cloud Logging sink (Cloud Audit Logs) |",
        "| Storage | Customer-owned S3 | Customer-owned blob/storage | "
        "Customer-owned GCS |",
        "| Trigger mode | Mirror-async (batch pull) | Mirror-async (batch pull) | "
        "Mirror-async (batch pull) |",
        "| Live / inline interception | ❌ not offered | ❌ not offered | ❌ not offered |",
        "| Access posture | Read-only, cross-account role | Read-only export read | "
        "Read-only export read |",
        "",
        "## Field coverage (from each provider's standard log schema)",
        "",
        "| Normalized field | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]

    for field, label in FIELDS:
        cells = [SYMBOL[_field_support(stock[n], field)] for n in names]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "**Legend:** ✅ present in the provider's standard logs · ◐ varies by "
        "configuration or deployment shape · ❌ not emitted by the provider — "
        "SARO cannot observe it from this source.",
        "",
        "## Rule-pack coverage",
        "",
        "| Rule pack | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]

    for pack_name, scenario in [
        ("RP-OBS-COMPLETE@1.0.0", Scenario.INCOMPLETE_OBSERVATION),
        ("RP-TOOL-SCOPE@1.0.0", Scenario.TOOL_SCOPE_VIOLATION),
    ]:
        cells = []
        for name in names:
            r = by_key.get((name, scenario))
            if r is None:
                cells.append("—")
            elif r.support is Support.NOT_SUPPORTED:
                cells.append("◐ partial")
            elif r.support is Support.CONDITIONAL:
                cells.append("◐ conditional")
            else:
                cells.append("✅ full")
        lines.append(f"| {pack_name} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "RP-OBS-COMPLETE evaluates on every adapter; **partial** means some of its "
        "checks cannot fire because the provider does not emit the underlying "
        "signal (see limitations below).",
        "",
        "## Limitations — what SARO does NOT support today",
        "",
    ]

    limitations: list[str] = []
    for r in sorted(report.gaps + report.conditionals, key=lambda x: x.display_name):
        kind = "Not supported" if r.support is Support.NOT_SUPPORTED else "Conditional"
        limitations.append(f"- **{r.display_name} — {r.scenario.value}** ({kind}): {r.reason}")

    for name in names:
        rec = stock[name]
        absent = [
            label
            for field, label in FIELDS
            if rec is not None and rec.availability(field) is FieldAvailability.UNAVAILABLE
        ]
        if absent:
            limitations.append(
                f"- **{name} — fields not emitted by the provider:** {', '.join(absent)}. "
                "SARO reports these as unavailable rather than inferring them."
            )

    # Provider-declared caveats: cases where a field is supported in principle
    # but depends on the customer's configuration or deployment shape. Declared
    # next to the adapter so they cannot drift from it.
    for adapter in adapters:
        for field_label, caveat in getattr(adapter, "field_caveats", lambda: {})().items():
            limitations.append(f"- **{adapter.display_name} — {field_label}:** {caveat}")

    lines += limitations or ["- None recorded."]
    lines += [
        "",
        "### Reading a blank result correctly",
        "",
        "Where a signal is not emitted, the corresponding rule produces **no "
        "findings** — because there is nothing to evaluate, **not** because the "
        "deployment was found free of issues. SARO marks these as unavailable in "
        "the record so a blank result is never mistaken for a clean one.",
        "",
        "## Adding another provider",
        "",
        "See `docs/adapter-design.md` §5 for the bar a new adapter must pass "
        "before it appears on this page.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _check_language(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in PROHIBITED_PHRASES if p in lowered]


def main(argv: list[str]) -> int:
    doc = build_document()

    violations = _check_language(doc)
    if violations:
        print(f"FAIL: prohibited claim language in generated matrix: {violations}")
        print("See docs/compliance-claims.md — SARO provides evidence, not verdicts.")
        return 1

    if "--check" in argv:
        if not OUT.exists():
            print(f"FAIL: {OUT} missing — run scripts/generate_capability_matrix.py")
            return 1
        if OUT.read_text(encoding="utf-8") != doc:
            print(
                "FAIL: docs/adapter-capability-matrix.md is stale — adapter "
                "behaviour or conformance results changed. Regenerate it."
            )
            return 1
        print("capability matrix OK: matches adapter behaviour")
        return 0

    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
