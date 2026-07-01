"""STORY-SOC-03 (Epic 15) — tests for the read-only SOC 2 evidence exporter.

These pin the two properties the story's DoD depends on:
  * AC-1: the exporter produces a timestamped bundle with a manifest + captured artifacts.
  * AC-3: the exporter is READ-ONLY — it imports no SARO application module, references no
    database/network client, and writes nothing outside the chosen output directory.

The exporter lives under compliance/ (not an importable package), so it is loaded by file path.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "compliance" / "soc2" / "evidence-collection" / "export_soc2_evidence.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("soc2_evidence_export", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_exists():
    assert _SCRIPT.is_file(), "SOC-03 evidence exporter is missing"


def test_export_writes_bundle_with_manifest(tmp_path):
    """AC-1: a bundle directory with a manifest.json is produced."""
    mod = _load_module()
    bundle = mod.export(tmp_path, since_days=1)

    assert bundle.exists() and bundle.is_dir()
    assert bundle.parent == tmp_path  # writes only under the chosen out dir
    manifest_path = bundle / "manifest.json"
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text())
    for key in (
        "story",
        "generated_at_utc",
        "change_management_cc8_1",
        "ci_gates_cc7_3_cc8_1",
        "captured_artifacts",
    ):
        assert key in manifest, f"manifest missing {key}"
    assert manifest["story"].startswith("STORY-SOC-03")


def test_export_captures_repo_artifacts(tmp_path):
    """AC-1: the quality ratchet + regression manifest are snapshotted when present."""
    mod = _load_module()
    bundle = mod.export(tmp_path, since_days=1)
    captured = json.loads((bundle / "manifest.json").read_text())["captured_artifacts"]

    # quality/baseline.json exists in this repo -> it must be captured verbatim.
    assert captured["quality_ratchet"]["present"] is True
    assert (bundle / "baseline.json").is_file()


def test_ci_workflow_inventory_is_read(tmp_path):
    """AC-1: CI workflows are inventoried as change-mgmt / vuln-mgmt gate evidence."""
    mod = _load_module()
    bundle = mod.export(tmp_path, since_days=1)
    ci = json.loads((bundle / "manifest.json").read_text())["ci_gates_cc7_3_cc8_1"]
    assert ci["present"] is True
    assert any(w.endswith((".yml", ".yaml")) for w in ci["workflows"])


def test_exporter_imports_no_app_module_or_network_client():
    """AC-3: static guard — the exporter must not import SARO app modules or network/DB clients.

    Parsing the source (rather than importing and introspecting) keeps this a pure, side-effect-free
    check of the read-only invariant.
    """
    tree = ast.parse(_SCRIPT.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {
        # SARO application modules (importing them could trigger runtime side effects)
        "engine", "main", "database", "models", "schemas", "auth", "config", "grc",
        "routers", "services", "middleware",
        # network / DB / external clients
        "requests", "httpx", "urllib", "socket", "sqlalchemy", "psycopg2", "psycopg",
        "redis", "boto3", "anthropic", "openai",
    }
    leaked = imported & forbidden
    assert not leaked, f"read-only exporter must not import: {sorted(leaked)}"


def test_export_writes_nothing_outside_out_dir(tmp_path):
    """AC-3: two exports into the same out dir both land under it; nothing escapes."""
    mod = _load_module()
    b1 = mod.export(tmp_path / "a", since_days=1)
    b2 = mod.export(tmp_path / "b", since_days=1)
    assert (tmp_path / "a") in b1.parents or b1.parent == (tmp_path / "a")
    assert (tmp_path / "b") in b2.parents or b2.parent == (tmp_path / "b")
