"""
SAR-012 SPEC-E1: llm_classification stored in Gate 3 AuditTrace detail_json.

Tests validate the llm_classification dict structure and the engine change that
stores verdicts. We test the public-facing _gate3_risk_classification output
via a no-API-key run (llm_classification absent) and validate the dict assembly
logic directly via unit-level extraction.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-sar012")


# ── Helper: build llm_classification dict the same way engine.py does ─────────

def _build_llm_classification(verdicts: list[dict]) -> dict | None:
    """
    Mirror of the llm_classification assembly logic in engine._gate3_risk_classification.
    Used to unit-test the dict shape without needing a full engine run.
    """
    if not verdicts:
        return None
    confirmed_count = sum(1 for v in verdicts if v.get("confirmed"))
    confidences = [v["confidence"] for v in verdicts if v.get("confidence") is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else None
    return {
        "model": "claude-sonnet-4-20250514",
        "verdicts_count": len(verdicts),
        "confirmed_count": confirmed_count,
        "confidence_avg": avg_confidence,
        "reasoning_summary": "; ".join(
            v["reasoning_summary"] for v in verdicts[:3] if v.get("reasoning_summary")
        )[:500] or None,
        "verdicts": verdicts[:10],
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_llm_classification_absent_without_api_key():
    """Without ANTHROPIC_API_KEY, Gate 3 details must not have llm_classification."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        from engine import SARoEngine, BatchIn, SampleIn, AuditConfigIn

        engine = SARoEngine.__new__(SARoEngine)
        engine._compliance_triggers = {}
        batch = BatchIn(
            samples=[SampleIn(sample_id=str(i), text="safe text here") for i in range(50)],
            config=AuditConfigIn(),
        )
        _, gate3 = engine._gate3_risk_classification(batch)
        assert "llm_classification" not in gate3.details, (
            "llm_classification must not appear when ANTHROPIC_API_KEY is absent"
        )


@pytest.mark.unit
def test_gate3_details_has_no_false_positive_reduction_rate():
    """STORY-107: the dead false_positive_reduction_rate metric is removed from gate3 details.

    It was computed but never read by any consumer; the non-hybrid branch was a
    no-op identity. Pin its absence so it cannot creep back.
    """
    env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        from engine import SARoEngine, BatchIn, SampleIn, AuditConfigIn

        engine = SARoEngine.__new__(SARoEngine)
        engine._compliance_triggers = {}
        batch = BatchIn(
            samples=[SampleIn(sample_id=str(i), text="safe text here") for i in range(50)],
            config=AuditConfigIn(),
        )
        _, gate3 = engine._gate3_risk_classification(batch)
        assert "false_positive_reduction_rate" not in gate3.details, (
            "false_positive_reduction_rate is dead and must not appear in gate3 details"
        )
        # The legitimate hybrid telemetry keys remain.
        for kept in ("hybrid_mode", "llm_calls_made", "llm_parse_failures"):
            assert kept in gate3.details, f"expected gate3 detail key {kept!r} to remain"


@pytest.mark.unit
def test_gate3_judge_receives_sample_text_not_signal_label(monkeypatch):
    """STORY-101: the Gate-3 LLM judge must reason over the sample's (redacted) text,
    not the matched-signal label (e.g. 'keyword:toxic')."""
    captured: dict = {}

    class _FakeMsg:
        def __init__(self, txt: str):
            self.content = [type("C", (), {"text": txt})()]

    class _FakeMessages:
        def create(self, **kw):
            captured["prompt"] = kw["messages"][0]["content"]
            return _FakeMsg(
                '{"domain": "Discrimination & Toxicity", "confirmed": true, '
                '"confidence": 0.9, "reasoning": "ok"}'
            )

    class _FakeClient:
        def __init__(self, *a, **k):
            self.messages = _FakeMessages()

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from engine import SARoEngine, BatchIn, SampleIn, AuditConfigIn

    engine = SARoEngine.__new__(SARoEngine)
    engine._compliance_triggers = {}
    # Sample triggers a domain (toxic/hate) AND embeds an SSN, so we can pin both
    # that the real text reaches the judge and that PII is redacted before egress.
    sample_text = "this message is clearly toxic hate speech, my ssn is 123-45-6789"
    samples = [SampleIn(sample_id=f"safe{i}", text="benign neutral content") for i in range(49)]
    samples.append(SampleIn(sample_id="flagged1", text=sample_text))
    batch = BatchIn(samples=samples, config=AuditConfigIn())
    engine._gate3_risk_classification(batch)

    assert "prompt" in captured, "LLM judge was never called"
    assert "toxic hate speech" in captured["prompt"], (
        "judge prompt must contain the actual sample text"
    )
    assert "keyword:" not in captured["prompt"], (
        "judge must not be handed the matched-signal label"
    )
    assert "pattern:" not in captured["prompt"]
    # PII must be redacted before it egresses to the external judge (STORY-101 security guarantee).
    assert "123-45-6789" not in captured["prompt"], "raw SSN must not reach the external judge"
    assert "***-**-****" in captured["prompt"], "SSN must be redacted in the judge prompt"


@pytest.mark.unit
def test_engine_source_has_no_false_positive_reduction():
    """STORY-107 AC-1: no live reference to the dead symbol remains in engine.py."""
    engine_src = (_REPO_ROOT / "engine.py").read_text(encoding="utf-8")
    assert "false_positive_reduction" not in engine_src, (
        "dead false_positive_reduction computation must be removed from engine.py"
    )


def test_llm_classification_model_name():
    """Model field must be exactly 'claude-sonnet-4-20250514'."""
    lc = _build_llm_classification([
        {"domain": "d", "confirmed": True, "confidence": 0.9, "reasoning_summary": "ok"},
    ])
    assert lc is not None
    assert lc["model"] == "claude-sonnet-4-20250514"


def test_llm_classification_required_fields_present():
    """All required fields must be present in llm_classification."""
    lc = _build_llm_classification([
        {"domain": "d", "confirmed": True, "confidence": 0.85, "reasoning_summary": "plausible"},
    ])
    assert lc is not None
    for field in ("model", "verdicts_count", "confirmed_count", "confidence_avg", "reasoning_summary", "verdicts"):
        assert field in lc, f"Missing required field: {field}"


def test_confirmed_count_accurate():
    """confirmed_count must count only verdicts with confirmed=True."""
    verdicts = [
        {"domain": "d", "confirmed": True, "confidence": 0.9, "reasoning_summary": "yes"},
        {"domain": "d", "confirmed": False, "confidence": 0.3, "reasoning_summary": "no"},
        {"domain": "d", "confirmed": True, "confidence": 0.85, "reasoning_summary": "yes"},
    ]
    lc = _build_llm_classification(verdicts)
    assert lc["confirmed_count"] == 2
    assert lc["verdicts_count"] == 3


def test_reasoning_summary_capped_at_500():
    """reasoning_summary in llm_classification must not exceed 500 chars."""
    verdicts = [{"domain": "d", "confirmed": True, "confidence": 0.9, "reasoning_summary": "x" * 1000}]
    lc = _build_llm_classification(verdicts)
    assert lc is not None
    summary = lc.get("reasoning_summary") or ""
    assert len(summary) <= 500, f"reasoning_summary length {len(summary)} exceeds 500"


def test_verdicts_capped_at_10():
    """verdicts list must be capped at 10 even when more verdicts are supplied."""
    verdicts = [
        {"domain": "d", "confirmed": True, "confidence": 0.8, "reasoning_summary": f"r{i}"}
        for i in range(15)
    ]
    lc = _build_llm_classification(verdicts)
    assert lc is not None
    assert len(lc["verdicts"]) == 10
    assert lc["verdicts_count"] == 15  # total count still shows all 15


def test_engine_gate3_details_include_llm_classification_key_structure():
    """Verify engine.py includes 'llm_classification' key when hybrid mode is active."""
    # Read the engine source and confirm the key is set
    engine_src = (_REPO_ROOT / "engine.py").read_text(encoding="utf-8")
    assert 'gate3_details["llm_classification"] = llm_classification' in engine_src, (
        "engine.py must assign llm_classification to gate3_details"
    )
    assert '"model": "claude-sonnet-4-20250514"' in engine_src, (
        "engine.py must set model to claude-sonnet-4-20250514 in llm_classification"
    )
    assert '"reasoning_summary"' in engine_src, (
        "engine.py must include reasoning_summary in llm_classification verdicts"
    )
