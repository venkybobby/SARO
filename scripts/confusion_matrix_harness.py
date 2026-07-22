#!/usr/bin/env python3
"""Confusion-matrix harness (STORY-378).

Measures each observation rule-pack against labeled ground truth and emits a
per-pack, per-tier, per-rule confusion matrix with precision / recall / F1.

Two properties are load-bearing:

* **Deterministic** (AC-1). Evaluation is the pure rule engine — no model calls
  (INV-1) — over a deterministic labeled corpus, so the same inputs yield the
  same matrix every run. That is what makes a trend meaningful rather than noise.

* **Report-only until the bar is signed** (AC-3). The pass/fail verdict comes
  from ``services.validation_bar``, which returns ``None`` thresholds unless an
  owner has signed the completion bar (STORY-377). While unsigned, the harness
  reports the real rates and marks the verdict ``report_only`` — it *cannot*
  fail a build against thresholds SARO set for itself. Signing later flips it to
  enforcing with no change here.

Usage:
    python scripts/confusion_matrix_harness.py                 # write artifact + trend
    python scripts/confusion_matrix_harness.py --check         # fail only if the bar is SIGNED and unmet
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.contract import NormalizedInvocationRecord  # noqa: E402
from rule_packs.observation.evaluate import evaluate_record  # noqa: E402
from rule_packs.observation.loader import load_pack  # noqa: E402
import services.validation_bar as validation_bar  # noqa: E402

CORPUS = ROOT / "tests" / "fixtures" / "validation" / "t1_labeled.jsonl"
OUT_DIR = ROOT / "quality" / "validation"
MATRIX_OUT = OUT_DIR / "confusion-latest.json"
TREND_OUT = OUT_DIR / "trend.jsonl"

PACKS = {
    "RP-OBS-COMPLETE@1.0.0": ROOT / "rule_packs" / "observation" / "rp_obs_complete" / "1.0.0" / "pack.yaml",
    "RP-TOOL-SCOPE@1.0.0": ROOT / "rule_packs" / "observation" / "rp_tool_scope" / "1.0.0" / "pack.yaml",
}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def add(self, other: "Counts") -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        self.tn += other.tn

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return round(self.tp / denom, 4) if denom else None

    @property
    def recall(self) -> float | None:
        denom = self.tp + self.fn
        return round(self.tp / denom, 4) if denom else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if not p or not r:
            return None
        return round(2 * p * r / (p + r), 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "precision": self.precision, "recall": self.recall, "f1": self.f1,
        }


def _load_labeled() -> list[dict]:
    return [json.loads(ln) for ln in CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _evaluate(pack_path: Path, record_dict: dict, allowed_tools: list[str]) -> set[str]:
    pack = load_pack(pack_path)
    if pack.name == "RP-TOOL-SCOPE":
        pack = pack.with_allowed_tools(allowed_tools)
    record = NormalizedInvocationRecord.model_validate(record_dict)
    return {f.rule_id for f in evaluate_record(record, pack)}


def compute_matrix() -> dict[str, Any]:
    items = _load_labeled()

    # Universe of rule ids per pack, so a "should not fire" case can count a TN.
    rule_universe = {
        ref: {r.rule_id for r in load_pack(path).rules} for ref, path in PACKS.items()
    }

    per_rule: dict[str, dict[str, Counts]] = {ref: {} for ref in PACKS}
    per_pack: dict[str, Counts] = {ref: Counts() for ref in PACKS}

    for item in items:
        record = item["record"]
        allowed = item.get("allowed_tools", [])
        for ref, path in PACKS.items():
            expected = set(item["expected"].get(ref, []))
            actual = _evaluate(path, record, allowed)
            for rule_id in rule_universe[ref]:
                c = per_rule[ref].setdefault(rule_id, Counts())
                exp, act = rule_id in expected, rule_id in actual
                if exp and act:
                    c.tp += 1
                elif act and not exp:
                    c.fp += 1
                elif exp and not act:
                    c.fn += 1
                else:
                    c.tn += 1

    for ref in PACKS:
        for c in per_rule[ref].values():
            per_pack[ref].add(c)

    return {
        "schema": "saro.confusion-matrix.v1",
        "tier": "T1",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "corpus_records": len(items),
        "packs": {
            ref: {
                "overall": per_pack[ref].as_dict(),
                "rules": {rid: per_rule[ref][rid].as_dict() for rid in sorted(per_rule[ref])},
            }
            for ref in PACKS
        },
    }


def apply_bar(matrix: dict[str, Any]) -> dict[str, Any]:
    """Attach a verdict. Report-only unless a signed bar is in force."""
    thresholds = validation_bar.active_thresholds()
    matrix["bar_status"] = validation_bar.status()
    if thresholds is None:
        matrix["verdict"] = "report_only"
        matrix["verdict_note"] = (
            "No signed completion bar in force (STORY-377 awaiting sign-off). "
            "Rates are reported; no pass/fail is asserted."
        )
        return matrix

    failures: list[str] = []
    for ref, packname in (("RP-OBS-COMPLETE@1.0.0", "RP-OBS-COMPLETE"), ("RP-TOOL-SCOPE@1.0.0", "RP-TOOL-SCOPE")):
        tier_th = (thresholds.get(packname) or {}).get("T1")
        if not tier_th:
            continue
        overall = matrix["packs"][ref]["overall"]
        for metric in ("precision", "recall"):
            floor = tier_th.get(metric)
            got = overall.get(metric)
            if floor is not None and got is not None and got < floor:
                failures.append(f"{packname} T1 {metric} {got} < {floor}")
    matrix["verdict"] = "fail" if failures else "pass"
    matrix["failures"] = failures
    return matrix


def main(argv: list[str]) -> int:
    matrix = apply_bar(compute_matrix())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MATRIX_OUT.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Trend: one compact line per run so regressions are diffable (AC-4). The
    # generated_at timestamp is excluded from the trend key so identical rates
    # do not churn the diff.
    trend_line = {
        "tier": matrix["tier"],
        "bar_status": matrix["bar_status"],
        "verdict": matrix["verdict"],
        "packs": {
            ref: matrix["packs"][ref]["overall"] for ref in PACKS
        },
    }
    with TREND_OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(trend_line, sort_keys=True) + "\n")

    for ref in PACKS:
        o = matrix["packs"][ref]["overall"]
        print(f"{ref}: precision={o['precision']} recall={o['recall']} f1={o['f1']}")
    print(f"bar: {matrix['bar_status']} · verdict: {matrix['verdict']}")

    # Fail the build ONLY when a signed bar is unmet. An unsigned bar is never
    # enforced — this is the AC-3 guarantee, made concrete.
    if "--check" in argv and matrix["verdict"] == "fail":
        print("FAIL: signed completion bar not met:")
        for f in matrix.get("failures", []):
            print(f"  {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
