"""STORY-363 — secret-scanning gate wiring stays intact.

These tests pin the *configuration* of the gitleaks gate: the canary fixture
really is credential-shaped (so the default ruleset must flag it), the repo
config allowlists ONLY the canary path, and ci.yml keeps the blocking
current-tree scan plus the self-test step. The behavioral proof (gitleaks
actually failing on the canary) runs in CI where the binary exists.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AWS_KEY_RE = re.compile(r"\b(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b")


def test_canary_fixture_is_credential_shaped():
    canary = ROOT / "tests" / "fixtures" / "gitleaks_canary" / "seeded_secret.txt"
    assert canary.exists(), "seeded canary fixture missing — CI self-test would vacuously pass"
    assert AWS_KEY_RE.search(canary.read_text(encoding="utf-8")), (
        "canary no longer matches the AWS access-key pattern; the self-test "
        "would stop proving the gate fires"
    )


def test_gitleaks_config_allowlists_only_the_canary():
    cfg = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    assert "useDefault = true" in cfg
    # every allowlisted path must be the canary dir — no blanket test exemption
    paths = re.findall(r"'''(.+?)'''", cfg)
    assert paths, "gitleaks allowlist should exist (for the canary) — did the config get emptied?"
    for p in paths:
        assert "gitleaks_canary" in p, f"unexpected allowlist path {p!r} — only the canary may be exempt"


def test_ci_has_blocking_scan_and_self_test():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "secret-scan:" in ci
    blocking = re.search(r"Current-tree scan \(BLOCKING\)[\s\S]{0,200}?gitleaks detect --no-git", ci)
    assert blocking, "blocking current-tree gitleaks scan missing from ci.yml"
    assert "gitleaks_canary" in ci, "canary self-test step missing from ci.yml"
    # the blocking step must NOT be continue-on-error
    block_section = ci[ci.index("Current-tree scan (BLOCKING)"):]
    first_step = block_section.split("- name:")[0]
    assert "continue-on-error" not in first_step, "blocking scan was made non-blocking"
