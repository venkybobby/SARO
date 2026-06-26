"""Unit tests for post-merge branch cleanup (scripts/post_merge_cleanup.py).

Pure selection logic only — no git network calls.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "post_merge_cleanup", ROOT / "scripts" / "post_merge_cleanup.py"
)
assert _spec is not None and _spec.loader is not None
pmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pmc)


def test_is_protected_exact_and_glob():
    assert pmc.is_protected("main", pmc.DEFAULT_PROTECTED)
    assert pmc.is_protected("develop", pmc.DEFAULT_PROTECTED)
    assert not pmc.is_protected("feature/x", pmc.DEFAULT_PROTECTED)
    assert pmc.is_protected("release/8.0", ("release/*",))


def test_select_prunable_excludes_base_and_protected():
    merged = ["main", "develop", "feature/a", "fix/b", "feature/a"]
    result = pmc.select_prunable(merged, base="main", protected_globs=pmc.DEFAULT_PROTECTED)
    assert result == ["feature/a", "fix/b"]  # base + develop removed, dedup applied


def test_select_prunable_honors_custom_protect_glob():
    merged = ["feature/a", "keep/important", "keep/also"]
    result = pmc.select_prunable(
        merged, base="main", protected_globs=pmc.DEFAULT_PROTECTED + ("keep/*",)
    )
    assert result == ["feature/a"]


def test_select_prunable_empty():
    assert pmc.select_prunable(["main"], base="main", protected_globs=pmc.DEFAULT_PROTECTED) == []


def test_select_prunable_strips_whitespace():
    result = pmc.select_prunable(["  feature/a  ", ""], base="main",
                                 protected_globs=pmc.DEFAULT_PROTECTED)
    assert result == ["feature/a"]


# --- CLI (main) ---------------------------------------------------------------

def test_main_dry_run_lists_candidates(monkeypatch, capsys):
    monkeypatch.setattr(pmc, "merged_remote_branches", lambda base: ["main", "feature/a"])
    assert pmc.main(["--base", "main"]) == 0
    out = capsys.readouterr().out
    assert "Would delete: feature/a" in out
    assert "Dry-run" in out


def test_main_apply_deletes(monkeypatch, capsys):
    deleted: list[str] = []
    monkeypatch.setattr(pmc, "merged_remote_branches", lambda base: ["feature/a", "automation/x"])
    monkeypatch.setattr(pmc, "delete_remote_branch", lambda b: deleted.append(b))
    # automation/* is protected via the CLI default in the workflow; here we pass it explicitly.
    assert pmc.main(["--apply", "--protect", "automation/*"]) == 0
    assert deleted == ["feature/a"]


def test_main_nothing_to_prune(monkeypatch, capsys):
    monkeypatch.setattr(pmc, "merged_remote_branches", lambda base: ["main"])
    assert pmc.main([]) == 0
    assert "No merged feature branches" in capsys.readouterr().out


def test_main_handles_git_failure(monkeypatch):
    import subprocess

    def boom(_base):
        raise subprocess.CalledProcessError(1, "git", stderr="boom")

    monkeypatch.setattr(pmc, "merged_remote_branches", boom)
    assert pmc.main([]) == 1
