#!/usr/bin/env python3
"""Deterministic labeled validation corpus (STORY-378, tier T1).

A confusion matrix needs ground truth: for each record, which rules *should*
fire. The synthetic adapter corpora plant scenarios but carry no per-rule
labels, so this builds a small, explicit, labeled T1 set — every record states
the rule_ids that ought to fire, so the harness can compare actual against
expected and count TP/FP/FN/TN.

Fully seed-derived and deterministic (AC-1): the same build produces a
byte-identical fixture, which is what makes the confusion matrix reproducible.
Synthetic and body-free, so no PHI is possible (INV-2).

Labels are deliberately hand-authored against the packs' documented semantics —
they are the *oracle*, independent of the implementation, so a rule that regresses
is caught by the label disagreeing rather than by the label tracking the bug.

Usage:
    python scripts/build_validation_corpus.py            # write the fixture
    python scripts/build_validation_corpus.py --check    # verify up to date
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "validation" / "t1_labeled.jsonl"

BASE_TIME = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
ALLOWED_TOOLS = ["search_kb", "lookup_record"]


def _rec(
    i: int,
    *,
    request_id: str = "req",
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
    operation: str = "Converse",
    input_tokens: int | None = 10,
    output_tokens: int | None = 20,
    truncated: bool = False,
    stop_reason: str | None = None,
    error_code: str | None = None,
    tools: list[dict] | None = None,
    availability: dict | None = None,
) -> dict[str, Any]:
    """One normalized-record-shaped dict (matches adapters.contract fields)."""
    ts = BASE_TIME.replace(microsecond=i)
    return {
        "contract_version": "1.0.0",
        "provenance": {"adapter_id": "validation-t1", "cursor": f"t1:L{i}", "source_uri": None, "record_hash": None},
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "request_id": f"{request_id}-{i}",
        "model_id": model_id,
        "operation": operation,
        "region": "us-east-1",
        "timestamp": ts.isoformat(),
        "input_token_count": input_tokens,
        "output_token_count": output_tokens,
        "stop_reason": stop_reason,
        "truncated": truncated,
        "error_code": error_code,
        "tools": tools or [],
        "field_availability": availability or {},
    }


def _item(record: dict, obs: list[str], tool: list[str], allowed_tools: list[str]) -> dict:
    """A labeled item: record + the rule_ids that SHOULD fire per pack."""
    return {
        "record": record,
        "allowed_tools": allowed_tools,
        "expected": {
            "RP-OBS-COMPLETE@1.0.0": sorted(obs),
            "RP-TOOL-SCOPE@1.0.0": sorted(tool),
        },
    }


def generate_corpus() -> list[dict]:
    items: list[dict] = []
    i = 0

    # ── RP-OBS-COMPLETE positives ───────────────────────────────────────────
    # Clean, complete record — nothing should fire.
    items.append(_item(_rec(i), obs=[], tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Missing required identity field (model_id empty) → OBS-REQUIRED-FIELDS-1.
    items.append(_item(_rec(i, model_id=""), obs=["OBS-REQUIRED-FIELDS-1"], tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Absent token counts → OBS-TOKEN-COUNTS-1.
    items.append(_item(_rec(i, input_tokens=None, output_tokens=None), obs=["OBS-TOKEN-COUNTS-1"], tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Truncated output → OBS-TRUNCATED-OUTPUT-1.
    items.append(_item(_rec(i, truncated=True, stop_reason="max_tokens"), obs=["OBS-TRUNCATED-OUTPUT-1"], tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Error status → OBS-ERROR-INVOCATION-1.
    items.append(_item(_rec(i, error_code="ThrottlingException"), obs=["OBS-ERROR-INVOCATION-1"], tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Combined: truncated AND error AND no tokens → three fire.
    items.append(_item(
        _rec(i, input_tokens=None, output_tokens=None, truncated=True, stop_reason="max_tokens", error_code="500"),
        obs=["OBS-TOKEN-COUNTS-1", "OBS-TRUNCATED-OUTPUT-1", "OBS-ERROR-INVOCATION-1"],
        tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # ── RP-TOOL-SCOPE ───────────────────────────────────────────────────────
    # In-scope tool use → nothing fires.
    items.append(_item(
        _rec(i, tools=[{"name": "search_kb", "offered": True, "invoked": True}]),
        obs=[], tool=[], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Out-of-scope INVOKED → TOOL-SCOPE-VIOLATION-1.
    items.append(_item(
        _rec(i, tools=[{"name": "delete_everything", "offered": True, "invoked": True}]),
        obs=[], tool=["TOOL-SCOPE-VIOLATION-1"], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Out-of-scope OFFERED but not invoked → TOOL-SCOPE-OFFERED-1.
    items.append(_item(
        _rec(i, tools=[{"name": "wire_transfer", "offered": True, "invoked": False}]),
        obs=[], tool=["TOOL-SCOPE-OFFERED-1"], allowed_tools=ALLOWED_TOOLS))
    i += 1

    # Tools used but tenant declared NO policy → TOOL-POLICY-ABSENT-1.
    items.append(_item(
        _rec(i, tools=[{"name": "anything", "offered": True, "invoked": True}]),
        obs=[], tool=["TOOL-POLICY-ABSENT-1"], allowed_tools=[]))
    i += 1

    # No tools, no policy → nothing fires (absence of policy is not yet a gap).
    items.append(_item(_rec(i), obs=[], tool=[], allowed_tools=[]))
    i += 1

    return items


def render(items: list[dict]) -> str:
    return "\n".join(json.dumps(it, sort_keys=True, ensure_ascii=True) for it in items) + "\n"


def main(argv: list[str]) -> int:
    content = render(generate_corpus())
    if "--check" in argv:
        if not FIXTURE.exists():
            print(f"FAIL: {FIXTURE} missing — run scripts/build_validation_corpus.py")
            return 1
        if FIXTURE.read_text(encoding="utf-8") != content:
            print("FAIL: labeled corpus is stale or the builder is non-deterministic")
            return 1
        print(f"validation corpus OK: {len(content.splitlines())} labeled records")
        return 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(content, encoding="utf-8")
    print(f"wrote {FIXTURE} ({len(content.splitlines())} labeled records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
