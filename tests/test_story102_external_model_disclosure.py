"""STORY-102: the external-model posture must be disclosed consistently.

SARO's core scoring never calls an external model; the optional Gate-3 LLM-judge
does, only when its API key is set. These tests pin that the disclosure exists in
the authoritative places and that the model is configurable — so the stated posture
and the actual behavior cannot silently drift apart again.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent


@pytest.mark.unit
def test_matrix_documents_optional_gate3_judge():
    matrix = (_ROOT / "docs" / "COMPLIANCE_CLAIMS_MATRIX.md").read_text(encoding="utf-8")
    assert "External Model Usage" in matrix, "matrix must have the External Model Usage section"
    assert "SARO_LLM_JUDGE_MODEL" in matrix, "matrix must document the configurable model env var"
    assert "off-by-default" in matrix or "off by default" in matrix, (
        "matrix must state the judge is off by default"
    )
    # The disclosure must scope the egress to redacted text, not raw PII.
    assert "PII-redacted" in matrix or "redact" in matrix.lower(), (
        "matrix must state only redacted text is sent to the judge"
    )


@pytest.mark.unit
def test_claude_md_discloses_the_exception():
    claude_md = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    # Constraint #1 must reference the disclosed optional judge, not state an unqualified absolute.
    assert "core scoring never calls external AI models" in claude_md
    assert "SARO_LLM_JUDGE_MODEL" in claude_md


@pytest.mark.unit
def test_no_unqualified_never_calls_external_ai_models():
    """STORY-102 AC-2: every authoritative restatement of the posture must carry the
    carve-out, so the single source of truth can't be silently contradicted.

    Doomed Streamlit (frontend/tabs/*) and the VeriAegis landing are excluded —
    they are deleted by STORY-105/106. Story spec docs are excluded (they quote the
    old phrasing while describing this very fix).
    """
    phrase = "never calls external AI models"
    markers = (
        "core scoring",
        "optional",
        "off by default",
        "off-by-default",
        "gate-3",
        "external model usage",
    )
    skip = (".claude/worktrees", "frontend/tabs", "veriaegis-landing", "specs/stories", "node_modules")
    targets: list[Path] = [_ROOT / "CLAUDE.md", _ROOT / "schemas.py"]
    for g in (
        ".cursor/rules/*.mdc",
        ".github/workflows/*.yml",
        ".claude/skills/**/SKILL.md",
        "routers/**/*.py",
        "services/**/*.py",
        "frontend/src/**/*.jsx",
        "frontend/src/**/*.js",
    ):
        targets.extend(_ROOT.glob(g))

    offenders: list[str] = []
    for f in targets:
        if not f.is_file():
            continue
        rel = f.relative_to(_ROOT).as_posix()
        if any(s in rel for s in skip):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if phrase in line and not any(m in line.lower() for m in markers):
                offenders.append(f"{rel}:{i}")
    assert not offenders, (
        f"unqualified '{phrase}' must carry the Gate-3 carve-out: {offenders}"
    )


@pytest.mark.unit
def test_engine_judge_model_and_provider_are_config_driven():
    from engine import LLM_JUDGE_MODEL, LLM_JUDGE_PROVIDER

    assert LLM_JUDGE_PROVIDER == "anthropic", "default provider must remain anthropic"
    assert LLM_JUDGE_MODEL == "claude-sonnet-4-20250514", "default model unchanged"
    engine_src = (_ROOT / "engine.py").read_text(encoding="utf-8")
    # The model literal must not be hardcoded at the call site anymore.
    assert 'model="claude-sonnet-4-20250514"' not in engine_src, (
        "Gate-3 judge model must be config-driven, not a hardcoded literal"
    )
