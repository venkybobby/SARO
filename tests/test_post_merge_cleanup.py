"""Unit tests for post-merge branch cleanup (scripts/post_merge_cleanup.py).

Pure selection logic only — no git or GitHub-API network calls (those are
monkeypatched in the CLI tests).
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


def test_extract_merged_head_refs_filters_unmerged():
    prs = [
        {"merged_at": "2026-06-26T00:00:00Z", "head": {"ref": "feature/a"}},
        {"merged_at": None, "head": {"ref": "feature/closed-not-merged"}},
        {"merged_at": "2026-06-25T00:00:00Z", "head": {"ref": "fix/b"}},
        {"merged_at": "2026-06-24T00:00:00Z", "head": {}},  # missing ref -> skipped
    ]
    assert pmc.extract_merged_head_refs(prs) == ["feature/a", "fix/b"]


def test_candidate_branches_requires_merged_and_existing():
    merged = ["feature/a", "fix/b", "feature/gone"]
    existing = ["feature/a", "fix/b", "main"]  # feature/gone already deleted
    result = pmc.candidate_branches(merged, existing, base="main",
                                    protected_globs=pmc.DEFAULT_PROTECTED)
    assert result == ["feature/a", "fix/b"]


def test_candidate_branches_excludes_base_and_protected():
    merged = ["main", "develop", "feature/a", "feature/a"]
    existing = ["main", "develop", "feature/a"]
    result = pmc.candidate_branches(merged, existing, base="main",
                                    protected_globs=pmc.DEFAULT_PROTECTED)
    assert result == ["feature/a"]  # base + develop removed, dedup applied


def test_candidate_branches_honors_custom_protect_glob():
    merged = ["feature/a", "automation/x"]
    existing = ["feature/a", "automation/x"]
    result = pmc.candidate_branches(
        merged, existing, base="main",
        protected_globs=pmc.DEFAULT_PROTECTED + ("automation/*",))
    assert result == ["feature/a"]


def test_candidate_branches_empty():
    assert pmc.candidate_branches([], [], base="main",
                                  protected_globs=pmc.DEFAULT_PROTECTED) == []


# --- CLI (main) ---------------------------------------------------------------

def _patch_sources(monkeypatch, merged_refs, existing):
    monkeypatch.setattr(pmc, "existing_remote_branches", lambda: existing)
    monkeypatch.setattr(
        pmc, "fetch_merged_prs",
        lambda repo, base, token: [{"merged_at": "x", "head": {"ref": r}} for r in merged_refs],
    )


def test_main_dry_run_lists_candidates(monkeypatch, capsys):
    _patch_sources(monkeypatch, ["feature/a"], ["feature/a", "main"])
    assert pmc.main(["--base", "main", "--repo", "owner/repo"]) == 0
    out = capsys.readouterr().out
    assert "Would delete: feature/a" in out
    assert "Dry-run" in out


def test_main_apply_deletes(monkeypatch):
    deleted: list[str] = []
    _patch_sources(monkeypatch, ["feature/a", "automation/x"], ["feature/a", "automation/x"])
    monkeypatch.setattr(pmc, "delete_remote_branch", lambda b: deleted.append(b))
    assert pmc.main(["--apply", "--repo", "owner/repo", "--protect", "automation/*"]) == 0
    assert deleted == ["feature/a"]


def test_main_nothing_to_prune(monkeypatch, capsys):
    _patch_sources(monkeypatch, [], ["main"])
    assert pmc.main(["--repo", "owner/repo"]) == 0
    assert "No merged feature branches" in capsys.readouterr().out


def test_main_requires_repo(monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert pmc.main([]) == 1


def test_main_handles_api_failure(monkeypatch):
    monkeypatch.setattr(pmc, "existing_remote_branches", lambda: ["feature/a"])

    def boom(repo, base, token):
        raise pmc.requests.RequestException("boom")

    monkeypatch.setattr(pmc, "fetch_merged_prs", boom)
    assert pmc.main(["--repo", "owner/repo"]) == 1


def test_existing_remote_branches_strips_prefix_and_head(monkeypatch):
    monkeypatch.setattr(
        pmc, "_git",
        lambda *a: "  origin/HEAD -> origin/main\n  origin/main\n  origin/feature/a\n",
    )
    assert pmc.existing_remote_branches() == ["main", "feature/a"]


def test_fetch_merged_prs_paginates(monkeypatch):
    # Full first page (100) forces a second request; partial second page ends it.
    pages = {
        1: [{"merged_at": "x", "head": {"ref": f"b{i}"}} for i in range(100)],
        2: [{"merged_at": "x", "head": {"ref": "last"}}],
    }
    calls: list[int] = []

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    def fake_get(url, params, headers, timeout):
        calls.append(params["page"])
        return FakeResp(pages.get(params["page"], []))

    monkeypatch.setattr(pmc.requests, "get", fake_get)
    prs = pmc.fetch_merged_prs("owner/repo", "main", "tok")
    assert len(prs) == 101
    assert calls == [1, 2]  # stopped after the short second page
