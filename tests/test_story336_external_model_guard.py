"""STORY-336 — No-external-model-at-runtime invariant guard.

A static guard fails the moment a product/runtime-path module reaches a
third-party hosted model API. Self-hosted models are permitted; the legacy
engine.py Gate-3 judge is an explicit, documented allowlist exception
(COMPLIANCE_CLAIMS_MATRIX §SARO-102); the offline QA-lab package is exempt and
must be unreachable from product code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grc.guards.external_model import (
    DEFAULT_ALLOWLIST,
    LAB_PACKAGE,
    ExternalModelInvariantViolation,
    Violation,
    _validate_allowlist,
    assert_clean_product_path,
    default_product_roots,
    scan_paths,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# --- AC: the real product path is clean (engine.py allowlisted) --------------


def test_real_product_path_is_clean() -> None:
    # The full product/runtime path must pass: grc/ + routers/ + services/ are
    # external-model-free and engine.py's disclosed judge is allowlisted.
    assert_clean_product_path(repo_root=REPO_ROOT)


# --- AC: a deliberately added external-model call fails the guard ------------


def test_injected_external_import_is_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path, "rogue.py", "import anthropic\n\n\ndef run():\n    return anthropic\n"
    )
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert violations
    assert any(v.kind == "import" and v.name == "anthropic" for v in violations)


def test_injected_from_import_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "rogue.py", "from openai import OpenAI\n")
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert any(v.kind == "import" and v.name == "openai" for v in violations)


def test_hosted_endpoint_string_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "rogue.py", 'URL = "https://api.openai.com/v1/chat/completions"\n')
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert any(v.kind == "endpoint" for v in violations)


# --- AC: a self-hosted model call passes the guard --------------------------


def test_self_hosted_model_passes(tmp_path: Path) -> None:
    # A self-hosted runtime (ollama / a localhost inference endpoint) does not
    # transmit data to a third-party API and must not be flagged.
    _write(
        tmp_path,
        "local_nli.py",
        'import ollama\nENDPOINT = "http://localhost:11434/api/generate"\n',
    )
    assert scan_paths([tmp_path], repo_root=tmp_path) == []


# --- AC: the engine.py disclosed judge is allowlisted (not invisible) -------


def test_engine_judge_is_allowlisted_not_clean() -> None:
    engine = REPO_ROOT / "engine.py"
    # Without the allowlist, engine.py's disclosed Gate-3 judge IS a hit — proves
    # the guard sees it and the allowlist is a real, documented exception.
    raw = scan_paths([engine], repo_root=REPO_ROOT, allowlist=frozenset())
    assert any(v.kind == "import" and v.name == "anthropic" for v in raw)
    # With the default allowlist, engine.py is exempt.
    assert scan_paths([engine], repo_root=REPO_ROOT) == []
    assert "engine.py" in DEFAULT_ALLOWLIST


# --- AC: offline QA-lab package is proven unreachable from product code ------


def test_lab_import_from_product_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "leaky.py", f"import {LAB_PACKAGE}\n")
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert any(v.kind == "lab_import" for v in violations)


def test_lab_subpackage_import_from_product_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "leaky.py", f"from {LAB_PACKAGE}.judge import label\n")
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert any(v.kind == "lab_import" for v in violations)


# --- guard wiring ------------------------------------------------------------


def test_assert_raises_on_violation(tmp_path: Path) -> None:
    _write(tmp_path, "rogue.py", "import cohere\n")
    with pytest.raises(ExternalModelInvariantViolation) as exc:
        assert_clean_product_path(repo_root=tmp_path, roots=[tmp_path])
    assert "cohere" in str(exc.value)


def test_violation_is_immutable() -> None:
    v = Violation(path="x.py", lineno=1, kind="import", name="anthropic", detail="d")
    with pytest.raises((AttributeError, TypeError)):
        v.name = "openai"  # type: ignore[misc]


# --- hardening: review findings (HIGH-1, HIGH-2, MED-3) ----------------------


def test_default_scope_includes_top_level_files_and_middleware() -> None:
    # HIGH-1: config.py and the middleware package are runtime — they must be in
    # the default scan scope, not silently excluded by a fixed file list.
    roots = {r.name for r in default_product_roots(REPO_ROOT)}
    assert "config.py" in roots
    assert "middleware" in roots
    assert "engine.py" in roots


def test_new_top_level_module_is_in_scope(tmp_path: Path) -> None:
    # A brand-new top-level runtime module is scanned without touching the guard.
    _write(tmp_path, "settings.py", "import litellm\n")
    violations = scan_paths(
        default_product_roots(tmp_path), repo_root=tmp_path, allowlist=frozenset()
    )
    assert any(v.name == "litellm" for v in violations)


@pytest.mark.parametrize(
    "module",
    ["litellm", "langchain_openai", "langchain_anthropic", "google.genai", "vertexai"],
)
def test_modern_provider_on_ramps_flagged(tmp_path: Path, module: str) -> None:
    # HIGH-2: the dominant modern hosted-model on-ramps are on the denylist.
    _write(tmp_path, "rogue.py", f"import {module}\n")
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert violations, f"{module} should be flagged"


def test_bedrock_runtime_client_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "rogue.py", 'import boto3\nc = boto3.client("bedrock-runtime")\n')
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert any(v.kind == "endpoint" and "bedrock" in v.name for v in violations)


def test_unrelated_google_cloud_not_flagged(tmp_path: Path) -> None:
    # Dotted denylist entries must match exactly — no false positive on sibling
    # google.cloud.* packages.
    _write(tmp_path, "ok.py", "from google.cloud import storage\nimport google.auth\n")
    assert scan_paths([tmp_path], repo_root=tmp_path) == []


def test_dynamic_import_literal_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "rogue.py",
        'import importlib\nm = importlib.import_module("openai")\nn = __import__("cohere")\n',
    )
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    names = {v.name for v in violations}
    assert "openai" in names and "cohere" in names


def test_guards_dirname_not_skipped_outside_grc(tmp_path: Path) -> None:
    # MED-3: only grc/guards is skipped — a 'guards' dir elsewhere is still scanned.
    sub = tmp_path / "routers" / "guards"
    sub.mkdir(parents=True)
    (sub / "rogue.py").write_text("import anthropic\n", encoding="utf-8")
    violations = scan_paths([tmp_path], repo_root=tmp_path)
    assert any(v.name == "anthropic" for v in violations)


def test_default_allowlist_paths_exist() -> None:
    # Allowlist entries must resolve to real files, or the exemption is a no-op typo.
    assert _validate_allowlist(REPO_ROOT, DEFAULT_ALLOWLIST) == []
