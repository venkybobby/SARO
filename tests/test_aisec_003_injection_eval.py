"""STORY-AISEC-003 — adversarial prompt-injection eval corpus + benchmark.

Turns "we detect prompt injection" into a measured, regenerable precision/recall
number over a labeled, inert offline corpus. Fully offline/deterministic — no
network, no external model. Benchmarks the STORY-AISEC-001 detector.

  AC-1  each corpus sample carries a label + an obfuscation tag
  AC-2  evaluate() reports precision, recall, and a per-obfuscation breakdown
  AC-3  the benign near-miss set yields a reported false-positive rate
  AC-4  evaluation makes zero network / external-model calls
  AC-5  each class meets SARO's internal >=50-sample heuristic (SARO-002)
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from rule_packs.injection.detector import load_injection_pack
from rule_packs.injection.eval import (
    ATTACK_LABELS,
    BENIGN_LABEL,
    OBFUSCATIONS,
    SOURCES,
    CorpusSample,
    evaluate,
    load_corpus,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parent.parent
_CORPUS = _REPO / "saro-data-framework" / "corpora" / "injection_eval_corpus.jsonl"

_PACK = load_injection_pack()
_CORPUS_SAMPLES = load_corpus(_CORPUS)
_LABELS = ATTACK_LABELS | {BENIGN_LABEL}


# ── corpus shape (AC-1) ──────────────────────────────────────────────────────


def test_corpus_loads_and_is_labeled():
    assert _CORPUS_SAMPLES
    for s in _CORPUS_SAMPLES:
        assert isinstance(s, CorpusSample)
        assert s.label in _LABELS, f"bad label: {s.label!r}"
        assert s.obfuscation in OBFUSCATIONS, f"bad obfuscation: {s.obfuscation!r}"
        assert s.source in SOURCES, f"bad source: {s.source!r}"
        assert s.text.strip()


def test_floor_is_met_by_distinct_plain_seeds_not_padding():
    """AC-5: the >=50/class floor is met by DISTINCT plain seeds — independent
    samples, not encoding variants or trivial-suffix duplicates (reviewer #2).
    >=50 is SARO-002's INTERNAL heuristic, not a regulation."""
    distinct: dict[str, set[str]] = {}
    for s in _CORPUS_SAMPLES:
        if s.obfuscation == "plain":
            distinct.setdefault(s.label, set()).add(s.text)
    for label in _LABELS:
        assert len(distinct.get(label, set())) >= 50, (
            f"{label}: {len(distinct.get(label, set()))} distinct plain seeds < 50"
        )


def test_every_attack_class_has_a_held_out_generalization_subset():
    """Reviewer #1: positives are not all reverse-engineered from the detector."""
    held_out: dict[str, int] = {}
    for s in _CORPUS_SAMPLES:
        if s.label in ATTACK_LABELS and s.source == "held-out":
            held_out[s.label] = held_out.get(s.label, 0) + 1
    for label in ATTACK_LABELS:
        assert held_out.get(label, 0) >= 10, f"{label}: too few held-out seeds"


def test_corpus_readme_flags_internal_methodology():
    readme = _CORPUS.parent / "README.md"
    text = readme.read_text(encoding="utf-8").lower()
    assert "internal" in text and "50" in text
    # must not misattribute the threshold to a regulation
    assert "art. 10 requires 50" not in text


# ── metrics (AC-2, AC-3) ─────────────────────────────────────────────────────


def test_evaluate_reports_precision_recall_and_per_obfuscation():
    m = evaluate(_CORPUS_SAMPLES, _PACK)
    for frac in (m.precision, m.recall, m.false_positive_rate):
        assert 0.0 <= frac <= 1.0
    assert m.true_positives + m.false_negatives > 0  # there are attack samples
    # per-obfuscation breakdown present for every tag that appears among attacks
    attack_tags = {s.obfuscation for s in _CORPUS_SAMPLES if s.label in ATTACK_LABELS}
    for tag in attack_tags:
        assert tag in m.by_obfuscation
        assert 0.0 <= m.by_obfuscation[tag]["recall"] <= 1.0


def test_false_positive_rate_is_reported_for_benign_set():
    """AC-3: guards STORY-AISEC-001 AC-3 against silent regressions."""
    m = evaluate(_CORPUS_SAMPLES, _PACK)
    assert m.true_negatives + m.false_positives > 0  # there are benign samples
    assert 0.0 <= m.false_positive_rate <= 1.0


def test_targeted_recall_is_high_regression_signal():
    """The detector should catch most TARGETED payloads — a regression signal."""
    m = evaluate(_CORPUS_SAMPLES, _PACK)
    assert m.by_source["targeted"]["recall"] >= 0.8


def test_held_out_recall_is_reported_as_generalization_probe():
    """Held-out recall is REPORTED (honest generalization number), no floor —
    a low value is the expected, useful signal for a regex detector."""
    m = evaluate(_CORPUS_SAMPLES, _PACK)
    assert "held-out" in m.by_source
    assert 0.0 <= m.by_source["held-out"]["recall"] <= 1.0
    assert m.by_source["held-out"]["total"] > 0


# ── offline guarantee (AC-4) ─────────────────────────────────────────────────


def test_evaluate_makes_no_network_calls(monkeypatch):
    def _blocked(*a, **k):
        raise AssertionError("injection eval attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    evaluate(_CORPUS_SAMPLES, _PACK)  # completes with no network


def test_evaluate_is_deterministic():
    assert evaluate(_CORPUS_SAMPLES, _PACK) == evaluate(_CORPUS_SAMPLES, _PACK)
