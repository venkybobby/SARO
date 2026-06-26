"""Unit tests for the loop preflight guard (scripts/loop_guard.py) and the
limits/registry/workflow consistency that keeps the kill switch trustworthy.
"""

import importlib.util
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("loop_guard", ROOT / "scripts" / "loop_guard.py")
assert _spec is not None and _spec.loader is not None
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)

LIMITS_PATH = ROOT / "loops" / "limits.yaml"
REGISTRY_PATH = ROOT / "loops" / "registry.yaml"


@pytest.fixture(scope="module")
def limits():
    return lg.load_limits(LIMITS_PATH)


# --- evaluate() pure logic ----------------------------------------------------

def _limits(**loops):
    return {"kill_switch": False, "defaults": {"daily_run_cap": 24}, "loops": loops}


def test_kill_switch_file_halts():
    lim = _limits(x={"enabled": True})
    lim["kill_switch"] = True
    proceed, reason = lg.evaluate(lim, "x")
    assert proceed is False and "kill switch" in reason


def test_env_kill_halts_even_if_file_false():
    proceed, reason = lg.evaluate(_limits(x={"enabled": True}), "x", env_kill=True)
    assert proceed is False and "kill switch" in reason


def test_disabled_loop_halts():
    proceed, reason = lg.evaluate(_limits(x={"enabled": False}), "x")
    assert proceed is False and "disabled" in reason


def test_run_cap_halts_at_or_above_cap():
    lim = _limits(x={"enabled": True, "daily_run_cap": 3})
    assert lg.evaluate(lim, "x", runs_today=3)[0] is False
    assert lg.evaluate(lim, "x", runs_today=2)[0] is True


def test_run_cap_falls_back_to_default():
    lim = _limits(x={"enabled": True})  # no per-loop cap -> defaults.daily_run_cap = 24
    assert lg.evaluate(lim, "x", runs_today=24)[0] is False
    assert lg.evaluate(lim, "x", runs_today=23)[0] is True


def test_unknown_loop_allowed_by_default():
    proceed, reason = lg.evaluate(_limits(x={"enabled": True}), "not-configured")
    assert proceed is True and "default" in reason


def test_missing_runs_today_skips_cap():
    lim = _limits(x={"enabled": True, "daily_run_cap": 1})
    assert lg.evaluate(lim, "x", runs_today=None)[0] is True  # fail-open on cap only


# --- env_kill_engaged ---------------------------------------------------------

@pytest.mark.parametrize("val,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("", False), ("false", False),
])
def test_env_kill_engaged(val, expected):
    assert lg.env_kill_engaged({"SARO_LOOPS_KILL_SWITCH": val}) is expected


# --- runs_today (network mocked) ---------------------------------------------

def test_runs_today_counts_total(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"total_count": 7}

    monkeypatch.setattr(lg.requests, "get", lambda *a, **k: FakeResp())
    assert lg.runs_today("o/r", "w.yml", "tok") == 7


def test_runs_today_none_without_workflow():
    assert lg.runs_today("o/r", "", "tok") is None


def test_runs_today_none_on_api_error(monkeypatch):
    def boom(*a, **k):
        raise lg.requests.RequestException("down")

    monkeypatch.setattr(lg.requests, "get", boom)
    assert lg.runs_today("o/r", "w.yml", "tok") is None


# --- main() exit codes --------------------------------------------------------

def test_main_proceeds(monkeypatch, tmp_path, capsys):
    f = tmp_path / "limits.yaml"
    f.write_text(yaml.safe_dump({"kill_switch": False, "loops": {"x": {"enabled": True}}}))
    monkeypatch.delenv("SARO_LOOPS_KILL_SWITCH", raising=False)
    monkeypatch.setattr(lg, "runs_today", lambda *a: 0)
    assert lg.main(["x", "--limits", str(f)]) == lg.EXIT_PROCEED
    assert "PROCEED" in capsys.readouterr().out


def test_main_halts_on_kill_switch(monkeypatch, tmp_path, capsys):
    f = tmp_path / "limits.yaml"
    f.write_text(yaml.safe_dump({"kill_switch": True, "loops": {"x": {"enabled": True}}}))
    monkeypatch.delenv("SARO_LOOPS_KILL_SWITCH", raising=False)
    assert lg.main(["x", "--limits", str(f)]) == lg.EXIT_HALT
    assert "HALT" in capsys.readouterr().out


# --- limits <-> registry <-> workflows consistency ----------------------------

def test_limits_loop_ids_exist_in_registry(limits):
    with REGISTRY_PATH.open() as fh:
        registry = yaml.safe_load(fh)
    registry_ids = {loop["id"] for loop in registry["loops"]}
    for loop_id in (limits.get("loops") or {}):
        assert loop_id in registry_ids, f"limits id '{loop_id}' not in registry.yaml"


def test_limits_workflow_files_exist(limits):
    wf_dir = ROOT / ".github" / "workflows"
    for loop_id, cfg in (limits.get("loops") or {}).items():
        wf = cfg.get("workflow")
        assert wf, f"{loop_id}: missing workflow field"
        assert (wf_dir / wf).exists(), f"{loop_id}: workflow {wf} not found"
