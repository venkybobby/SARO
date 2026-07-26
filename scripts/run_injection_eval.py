#!/usr/bin/env python3
"""Run the offline prompt-injection benchmark (STORY-AISEC-003).

Loads the labeled corpus and the RP-PROMPT-INJECTION pack, measures the
detector's precision / recall / false-positive-rate + per-obfuscation recall, and
writes the metrics to saro-data-framework/output/injection_eval_batch.json.

Fully offline and deterministic — no network, no external model. Payloads are
DATA only; they are matched, never interpreted or executed.

    python scripts/run_injection_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rule_packs.injection.detector import load_injection_pack  # noqa: E402
from rule_packs.injection.eval import evaluate, load_corpus  # noqa: E402

_CORPUS = _REPO / "saro-data-framework" / "corpora" / "injection_eval_corpus.jsonl"
_OUT = _REPO / "saro-data-framework" / "output" / "injection_eval_batch.json"


def run() -> dict:
    pack = load_injection_pack()
    corpus = load_corpus(_CORPUS)
    metrics = evaluate(corpus, pack)
    report = {
        "benchmark": "prompt-injection-detector",
        "pack": f"{pack.name}@{pack.version}",
        "pack_hash": pack.pack_hash,
        "corpus": _CORPUS.relative_to(_REPO).as_posix(),
        "corpus_size": metrics.total,
        # No timestamp on purpose: the committed report must diff cleanly across
        # regenerations (NFR "regenerable and diffable"). Provenance is the pack
        # hash + corpus content, which are deterministic.
        "metrics": metrics.as_dict(),
        "note": (
            "Offline evaluation. The >=50-per-class floor is met by DISTINCT plain "
            "seeds and is an internal SARO methodology heuristic (SARO-002), not a "
            "regulatory threshold. 'targeted' recall is a regression signal; "
            "'held-out' recall is the honest generalization probe."
        ),
    }
    return report


def main() -> int:
    report = run()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    m = report["metrics"]
    print(
        f"injection eval: n={report['corpus_size']} "
        f"precision={m['precision']} recall={m['recall']} "
        f"fpr={m['false_positive_rate']} -> {_OUT.relative_to(_REPO).as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
