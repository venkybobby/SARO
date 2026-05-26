"""
S-002: HuggingFace Sampler Script — unit tests.

Tests that:
  1. The hf_sampler.py script is importable and has expected functions.
  2. Column resolution logic handles various dataset column patterns.
  3. Text extraction handles strings, lists, and dicts.
  4. requirements.txt includes datasets and huggingface-hub.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")


class TestHFSamplerImport:
    def test_script_importable(self):
        import scripts.hf_sampler as hf_sampler
        assert hasattr(hf_sampler, "main")
        assert hasattr(hf_sampler, "_insert_samples")
        assert hasattr(hf_sampler, "_load_dataset")

    def test_vertical_datasets_configured(self):
        from scripts.hf_sampler import _VERTICAL_DATASETS
        assert "healthcare" in _VERTICAL_DATASETS
        assert "finance" in _VERTICAL_DATASETS
        assert "legal" in _VERTICAL_DATASETS
        assert "general" in _VERTICAL_DATASETS


class TestColumnResolution:
    def test_resolve_explicit_columns(self):
        from scripts.hf_sampler import _resolve_columns
        row = {"prompt": "hello", "response": "world", "other": "stuff"}
        p, o = _resolve_columns(row, "prompt", "response")
        assert p == "prompt"
        assert o == "response"

    def test_resolve_default_prompt_column(self):
        from scripts.hf_sampler import _resolve_columns
        row = {"instruction": "do this", "output": "done"}
        p, o = _resolve_columns(row, None, "output")
        assert p == "instruction"
        assert o == "output"

    def test_resolve_fallback_to_first_column(self):
        from scripts.hf_sampler import _resolve_columns
        row = {"weird_col": "text", "another": "text2"}
        p, o = _resolve_columns(row, None, None)
        # Falls back to first column when no defaults match
        assert p in row
        assert o in row

    def test_missing_explicit_column_uses_default(self):
        from scripts.hf_sampler import _resolve_columns
        row = {"question": "hello", "answer": "world"}
        p, o = _resolve_columns(row, "nonexistent_col", "answer")
        assert p == "question"  # auto-detected
        assert o == "answer"


class TestTextExtraction:
    def test_extract_string(self):
        from scripts.hf_sampler import _extract_text
        assert _extract_text("  hello world  ") == "hello world"

    def test_extract_list_of_dicts_wildchat_style(self):
        from scripts.hf_sampler import _extract_text
        value = [
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "AI is..."},
        ]
        result = _extract_text(value)
        assert "[user]: What is AI?" in result
        assert "[assistant]: AI is..." in result

    def test_extract_list_of_strings(self):
        from scripts.hf_sampler import _extract_text
        result = _extract_text(["part1", "part2"])
        assert "part1" in result
        assert "part2" in result

    def test_extract_non_string_converts(self):
        from scripts.hf_sampler import _extract_text
        assert _extract_text(42) == "42"
        assert _extract_text(None) == "None"


class TestRequirementsTxt:
    def test_datasets_in_requirements(self):
        req_path = os.path.join(_REPO_ROOT, "requirements.txt")
        content = open(req_path).read()
        assert "datasets" in content, "datasets package missing from requirements.txt"

    def test_huggingface_hub_in_requirements(self):
        req_path = os.path.join(_REPO_ROOT, "requirements.txt")
        content = open(req_path).read()
        assert "huggingface-hub" in content, "huggingface-hub missing from requirements.txt"
