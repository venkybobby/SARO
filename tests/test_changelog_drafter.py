"""Unit tests for the changelog drafter (scripts/changelog_drafter.py).

Pure logic only — git history access is exercised in the workflow.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "changelog_drafter", ROOT / "scripts" / "changelog_drafter.py"
)
assert _spec is not None and _spec.loader is not None
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)


def test_parse_commit_with_scope():
    assert cd.parse_commit("feat(engine): add DIR caching") == {
        "type": "feat", "scope": "engine", "breaking": False, "desc": "add DIR caching",
    }


def test_parse_commit_breaking():
    parsed = cd.parse_commit("fix(api)!: drop legacy v0 endpoint")
    assert parsed["breaking"] is True
    assert parsed["type"] == "fix"
    assert parsed["scope"] == "api"


def test_parse_commit_no_scope():
    assert cd.parse_commit("docs: update README")["scope"] is None


@pytest.mark.parametrize("subject", [
    "not a conventional commit",
    "Merge branch 'main'",
    "WIP",
])
def test_parse_commit_rejects_non_conventional(subject):
    assert cd.parse_commit(subject) is None


def test_group_commits_collects_breaking_across_types():
    subjects = [
        "feat(a): one",
        "fix(b)!: two",
        "feat!: three",
        "chore: four",
        "garbage line",
    ]
    groups, breaking = cd.group_commits(subjects)
    assert len(groups["feat"]) == 2
    assert len(groups["fix"]) == 1
    assert len(groups["chore"]) == 1
    assert len(breaking) == 2


def test_render_changelog_orders_sections_and_headers():
    subjects = ["fix(x): a bug", "feat(y): a feature"]
    out = cd.render_changelog("v1.2.0", subjects, "2026-06-26")
    assert out.startswith("## v1.2.0 (2026-06-26)")
    # Features section must appear before Bug Fixes (SECTIONS order).
    assert out.index("### Features") < out.index("### Bug Fixes")
    assert "**y:** a feature" in out
    assert "**x:** a bug" in out


def test_render_changelog_breaking_section_first():
    out = cd.render_changelog("v2.0.0", ["feat(core)!: rewrite"], "2026-06-26")
    assert "### ⚠ BREAKING CHANGES" in out
    assert out.index("BREAKING CHANGES") < out.index("### Features")


def test_render_changelog_empty_range():
    out = cd.render_changelog("v1.0.1", ["just merging stuff"], "2026-06-26")
    assert "_No conventional commits in this range._" in out


# --- CLI (main) ---------------------------------------------------------------

def test_main_writes_output_file(monkeypatch, tmp_path):
    monkeypatch.setattr(cd, "last_tag", lambda: None)
    monkeypatch.setattr(cd, "commit_subjects", lambda r: ["feat(x): a", "fix: b"])
    out_file = tmp_path / "section.md"
    rc = cd.main(["--version", "v9.9.9", "--date", "2026-06-26", "--output", str(out_file)])
    assert rc == 0
    body = out_file.read_text()
    assert "v9.9.9 (2026-06-26)" in body
    assert "### Features" in body


def test_main_stdout_with_explicit_range(monkeypatch, capsys):
    monkeypatch.setattr(cd, "commit_subjects", lambda r: ["feat: x"])
    rc = cd.main(["--version", "v1.0.0", "--from", "HEAD~1", "--date", "2026-06-26"])
    assert rc == 0
    assert "v1.0.0" in capsys.readouterr().out


def test_main_handles_git_failure(monkeypatch):
    import subprocess

    def boom(_range):
        raise subprocess.CalledProcessError(1, "git", stderr="bad range")

    monkeypatch.setattr(cd, "last_tag", lambda: None)
    monkeypatch.setattr(cd, "commit_subjects", boom)
    assert cd.main(["--version", "v1", "--date", "2026-06-26"]) == 1
