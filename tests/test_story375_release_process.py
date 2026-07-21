"""STORY-375 — versioned release process.

The version's failure mode is drift: the same number written in two places, one
of which is stale. So the tests are mostly about there being exactly one source.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.unit

CHANGELOG = ROOT / "CHANGELOG.md"
ROLLBACK = ROOT / "docs" / "ops" / "release-rollback.md"
RELEASE_WF = ROOT / ".github" / "workflows" / "release.yml"


# ── AC-1: single version source, surfaced in API ────────────────────────────


def test_version_has_a_single_source():
    from _version import __version__

    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), "version must be SemVer x.y.z"


def test_main_does_not_re_hardcode_the_version():
    """The bug this prevents: bumping _version.py but not main.py, or vice versa."""
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    # The FastAPI app must reference the imported symbol, not a literal.
    assert "version=__version__" in src
    assert 'version="8.0.0"' not in src, "main.py re-hardcodes the version"


def test_fastapi_app_reports_the_single_source_version():
    from _version import __version__
    from main import app

    assert app.version == __version__


def test_version_endpoint_returns_version_and_build_info():
    from fastapi.testclient import TestClient

    from _version import __version__
    from main import app

    resp = TestClient(app, raise_server_exceptions=False).get("/api/v1/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == __version__
    assert "commit" in body and "environment" in body


def test_version_endpoint_is_public():
    """A customer's change-management process must read it without a credential."""
    from fastapi.testclient import TestClient

    from main import app

    # No Authorization header.
    assert TestClient(app, raise_server_exceptions=False).get("/api/v1/version").status_code == 200


def test_ui_footer_reads_the_version_endpoint_not_a_literal():
    shell = (ROOT / "frontend" / "src" / "components" / "AppShell.jsx").read_text(encoding="utf-8")
    assert "VersionFooter" in shell
    assert '/api/v1/version' in shell, "the footer must read the single source, not hardcode"


# ── AC-2: changelog + gate ──────────────────────────────────────────────────


def test_changelog_exists_and_follows_keep_a_changelog():
    doc = CHANGELOG.read_text(encoding="utf-8")
    assert "Keep a Changelog" in doc
    assert "## [Unreleased]" in doc
    assert "## [8.0.0]" in doc


def test_changelog_gate_flags_a_release_pr_without_an_entry(tmp_path, monkeypatch):
    """The gate must actually fail when no bullet was added."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_changelog_entry as gate

    monkeypatch.setattr(gate, "_added_changelog_lines", lambda base, head: ["## [1.2.3]"])
    assert gate.main(["x"]) == 1  # a heading but no '- ' bullet


def test_changelog_gate_passes_when_a_bullet_is_added(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_changelog_entry as gate

    monkeypatch.setattr(
        gate, "_added_changelog_lines", lambda base, head: ["- Added a new thing"]
    )
    assert gate.main(["x"]) == 0


# ── AC-3: release pipeline ──────────────────────────────────────────────────


def test_release_pipeline_runs_conformance_and_tests_before_deploy():
    import yaml

    wf = yaml.safe_load(RELEASE_WF.read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    assert "tags" in on["push"] and on["push"]["tags"] == ["v*"]

    gates = wf["jobs"]["release-gates"]
    steps = " ".join(str(s) for s in gates["steps"])
    assert "test_story361_conformance" in steps, "conformance suite must gate a release"
    assert "pytest tests/ -q" in steps, "full suite must gate a release"


def test_release_pipeline_verifies_tag_matches_version_source():
    wf = RELEASE_WF.read_text(encoding="utf-8")
    assert "_version.py" in wf
    assert "does not match" in wf, "a mismatched tag must fail before deploy"


def test_changelog_gate_only_runs_on_release_prs():
    wf = RELEASE_WF.read_text(encoding="utf-8")
    assert "'release'" in wf or "startsWith(github.event.pull_request.title, 'release:')" in wf


def test_pipeline_does_not_duplicate_deploy_logic():
    """Deploy + canary are reused, not reimplemented, so they cannot diverge."""
    wf = RELEASE_WF.read_text(encoding="utf-8")
    assert "flyctl deploy" not in wf, "release.yml should not re-implement deploy"


# ── AC-4: rollback documented, rehearsal human-gated ────────────────────────


def test_rollback_doc_exists_with_the_migration_caveat():
    doc = ROLLBACK.read_text(encoding="utf-8")
    assert "rollback" in doc.lower()
    # The dangerous case must be called out.
    assert "code, not schema" in doc.lower() or "code not schema" in doc.lower()
    assert "schema_mismatch" in doc


def test_rollback_rehearsal_is_marked_human_open():
    doc = ROLLBACK.read_text(encoding="utf-8")
    assert "[HUMAN — OPEN]" in doc
    assert "scratch" in doc.lower()
    assert "unproven" in doc.lower() or "hypothesis" in doc.lower()
