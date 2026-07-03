"""Unit tests for the loop run-log recorder (scripts/loop_runlog.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("loop_runlog", ROOT / "scripts" / "loop_runlog.py")
assert _spec is not None and _spec.loader is not None
rl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rl)


def test_format_entry_basic():
    row = rl.format_entry("2026-06-27T00:00:00Z", "dependency-sweeper", "42", "ok", "1 bump")
    assert row == "| 2026-06-27T00:00:00Z | dependency-sweeper | 42 | ok | 1 bump |"


def test_format_entry_escapes_pipes_and_newlines():
    row = rl.format_entry("t", "loop", "r", "ok", "a | b\nc")
    assert "\\|" in row
    assert "\n" not in row.rstrip("\n")


def test_format_entry_blanks_become_dash():
    row = rl.format_entry("t", "loop", "", "no-op", "")
    assert "| - | no-op | - |" in row


def test_ensure_log_creates_header(tmp_path):
    log = tmp_path / "run-log.md"
    rl.ensure_log(log)
    text = log.read_text()
    assert rl.TABLE_HEADER in text
    assert text.endswith(rl.TABLE_SEP + "\n")


def test_ensure_log_idempotent(tmp_path):
    log = tmp_path / "run-log.md"
    rl.ensure_log(log)
    rl.append_entry(log, "| x | y | z | ok | d |")
    rl.ensure_log(log)  # must not clobber existing content
    assert "| x | y | z | ok | d |" in log.read_text()


def test_append_entry_creates_then_appends(tmp_path):
    log = tmp_path / "sub" / "run-log.md"  # parent created on demand
    rl.append_entry(log, "| a | b | c | ok | one |")
    rl.append_entry(log, "| a | b | c | ok | two |")
    lines = log.read_text().splitlines()
    assert lines[-2].endswith("one |")
    assert lines[-1].endswith("two |")


def test_main_appends_and_writes_summary(tmp_path, monkeypatch, capsys):
    log = tmp_path / "run-log.md"
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_RUN_ID", "999")
    rc = rl.main(["post-merge-cleanup", "--outcome", "no-op", "--detail", "nothing to prune",
                  "--append", str(log), "--timestamp", "2026-06-27T01:02:03Z"])
    assert rc == 0
    row = "| 2026-06-27T01:02:03Z | post-merge-cleanup | 999 | no-op | nothing to prune |"
    assert row in log.read_text()
    assert row in summary.read_text()
    assert row in capsys.readouterr().out


def test_main_run_id_defaults_to_env(tmp_path, monkeypatch):
    log = tmp_path / "run-log.md"
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("GITHUB_RUN_ID", "abc123")
    rl.main(["ci-sweeper", "--append", str(log), "--timestamp", "t"])
    assert "| ci-sweeper | abc123 |" in log.read_text()
