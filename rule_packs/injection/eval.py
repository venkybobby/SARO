"""Offline benchmark of the prompt-injection detector (STORY-AISEC-003).

Loads a labeled, inert corpus and measures the STORY-AISEC-001 detector's
precision / recall / false-positive-rate, with a per-obfuscation recall
breakdown. Pure, offline, deterministic — no network, no external model. Payloads
in the corpus are DATA only; they are matched, never interpreted or executed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rule_packs.injection.detector import InjectionPack, scan

# Attack classes (a "positive" sample) vs the benign class (a "negative").
ATTACK_LABELS: frozenset[str] = frozenset({"injection", "jailbreak", "leakage"})
BENIGN_LABEL: str = "benign"
OBFUSCATIONS: frozenset[str] = frozenset(
    {"plain", "zero-width", "base64", "rot13", "homoglyph"}
)


# Provenance of an attack sample:
#   targeted  — phrased to hit the detector's rules (a REGRESSION signal)
#   held-out  — novel phrasing not derived from the rules (a GENERALIZATION probe)
#   benign    — negative sample
SOURCES: frozenset[str] = frozenset({"targeted", "held-out", "benign"})


@dataclass(frozen=True)
class CorpusSample:
    text: str
    label: str  # one of ATTACK_LABELS or BENIGN_LABEL
    obfuscation: str  # one of OBFUSCATIONS
    source: str = "targeted"  # one of SOURCES


@dataclass(frozen=True)
class EvalMetrics:
    total: int
    by_class: dict[str, int]
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    false_positive_rate: float
    # per-obfuscation recall over TARGETED attack samples only. The encoding
    # buckets (zero-width/base64/rot13/homoglyph) are each the same fixed 12-seed
    # subset, so they are mutually comparable; the 'plain' bucket spans all
    # targeted-plain seeds, so plain-vs-encoding is indicative, not same-payload.
    by_obfuscation: dict[str, dict[str, float]]
    # recall split by provenance: 'targeted' (regression) vs 'held-out'
    # (generalization). held-out recall is the honest real-world-ish signal.
    by_source: dict[str, dict[str, float]]

    @staticmethod
    def _round(d: dict[str, float]) -> dict[str, float]:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in d.items()}

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "by_class": self.by_class,
            "confusion": {
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
                "true_negatives": self.true_negatives,
            },
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "by_obfuscation": {
                t: self._round(d) for t, d in self.by_obfuscation.items()
            },
            "by_source": {s: self._round(d) for s, d in self.by_source.items()},
            "interpretation": (
                "Recall over 'targeted' payloads is a REGRESSION signal (payloads "
                "written to match the detector's rules). Recall over 'held-out' "
                "payloads is a GENERALIZATION probe (novel phrasings not derived "
                "from the rules) — the honest real-world-ish rate. Internal quality "
                "signal, not a certified detection rate."
            ),
        }


def load_corpus(path: str | Path) -> list[CorpusSample]:
    """Load the JSONL corpus. Each line: {text, label, obfuscation}."""
    samples: list[CorpusSample] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            samples.append(
                CorpusSample(
                    text=row["text"],
                    label=row["label"],
                    obfuscation=row.get("obfuscation", "plain"),
                    source=row.get("source", "targeted"),
                )
            )
    return samples


def _safe_div(num: int, den: int) -> float:
    return num / den if den else 0.0


def evaluate(corpus: list[CorpusSample], pack: InjectionPack) -> EvalMetrics:
    """Run the detector over every sample and compute confusion-based metrics.

    A sample is DETECTED when ``scan`` returns at least one indicator. An attack
    sample (label in ATTACK_LABELS) that is detected is a true positive; a benign
    sample that is detected is a false positive.
    """
    tp = fp = fn = tn = 0
    by_class: dict[str, int] = {}
    # per-obfuscation recall over TARGETED attack samples only: {tag: [det, total]}
    obf: dict[str, list[int]] = {}
    # per-source recall over attack samples: {source: [det, total]}
    src: dict[str, list[int]] = {}

    for s in corpus:
        by_class[s.label] = by_class.get(s.label, 0) + 1
        detected = bool(scan(s.text, pack))
        is_attack = s.label in ATTACK_LABELS
        if is_attack:
            src_slot = src.setdefault(s.source, [0, 0])
            src_slot[1] += 1
            # Obfuscation breakdown is targeted-only so encodings compare against
            # the same payloads; held-out samples are all 'plain' and would skew it.
            if s.source == "targeted":
                obf_slot = obf.setdefault(s.obfuscation, [0, 0])
                obf_slot[1] += 1
            if detected:
                tp += 1
                src_slot[0] += 1
                if s.source == "targeted":
                    obf[s.obfuscation][0] += 1
            else:
                fn += 1
        else:
            if detected:
                fp += 1
            else:
                tn += 1

    def _breakdown(counts: dict[str, list[int]]) -> dict[str, dict[str, float]]:
        return {
            key: {
                "detected": float(det),
                "total": float(tot),
                "recall": _safe_div(det, tot),
            }
            for key, (det, tot) in sorted(counts.items())
        }

    return EvalMetrics(
        total=len(corpus),
        by_class=dict(sorted(by_class.items())),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=_safe_div(tp, tp + fp),
        recall=_safe_div(tp, tp + fn),
        false_positive_rate=_safe_div(fp, fp + tn),
        by_obfuscation=_breakdown(obf),
        by_source=_breakdown(src),
    )
