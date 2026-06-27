"""Unit tests for loop readiness auditing (scripts/loop_audit.py).

Includes the enforceable invariant that the live registry has no over-provisioned
loop — the same check CI runs with --strict.
"""

import importlib.util
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("loop_audit", ROOT / "scripts" / "loop_audit.py")
assert _spec is not None and _spec.loader is not None
la = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(la)


def _wf_loop(**over):
    base = {
        "id": "x", "description": "d", "category": "c", "trigger": "schedule",
        "cadence": "0 0 * * *", "implementation": "wf.yml",
        "escalation": "human merges", "verification": "reviewer approves",
        "maturity": "L1",
    }
    base.update(over)
    return base


# --- _has_review --------------------------------------------------------------

def test_has_review_detects_markers():
    assert la._has_review({"verification": "Independent reviewer + security-auditor"})
    assert la._has_review({"escalation": "escalate to a human review"})
    assert not la._has_review({"verification": "green CI is terminal", "escalation": "retry"})


# --- _qualified_level ---------------------------------------------------------

def test_qualified_l0_when_missing_base():
    dims = {"purpose": False, "scheduling": True, "implementation": True,
            "human_handoff": True, "verification": True, "maker_checker": True,
            "cost_limits": True, "observability": True}
    assert la._qualified_level(dims) == "L0"


def test_qualified_l1_without_verification_or_limits():
    dims = {"purpose": True, "scheduling": True, "implementation": True,
            "human_handoff": True, "verification": True, "maker_checker": True,
            "cost_limits": False, "observability": True}
    assert la._qualified_level(dims) == "L1"


def test_qualified_l2_without_maker_checker():
    dims = {"purpose": True, "scheduling": True, "implementation": True,
            "human_handoff": True, "verification": True, "maker_checker": False,
            "cost_limits": True, "observability": True}
    assert la._qualified_level(dims) == "L2"


def test_qualified_l3_full():
    dims = {"purpose": True, "scheduling": True, "implementation": True,
            "human_handoff": True, "verification": True, "maker_checker": True,
            "cost_limits": True, "observability": True}
    assert la._qualified_level(dims) == "L3"


def test_na_dimensions_count_as_pass():
    # Non-workflow loop: cost_limits/observability are None and must not block L3.
    dims = {"purpose": True, "scheduling": True, "implementation": True,
            "human_handoff": True, "verification": True, "maker_checker": True,
            "cost_limits": None, "observability": None}
    assert la._qualified_level(dims) == "L3"


# --- audit_loop ---------------------------------------------------------------

def test_audit_flags_over_provisioned():
    loop = _wf_loop(maturity="L3", verification="green CI is terminal", escalation="retry")
    r = la.audit_loop(loop, limits_loops={"x": {"daily_run_cap": 4}}, runlog_wired=set())
    assert r["over_provisioned"] is True
    assert "observability" in r["gaps"]


def test_audit_not_over_when_declared_within_qualified():
    loop = _wf_loop(maturity="L2", verification="reviewer approves")
    r = la.audit_loop(loop, limits_loops={"x": {"daily_run_cap": 4}}, runlog_wired={"x"})
    assert r["over_provisioned"] is False


def test_audit_missing_limits_means_no_cost_dimension():
    loop = _wf_loop(maturity="L2", verification="reviewer approves")
    r = la.audit_loop(loop, limits_loops={}, runlog_wired={"x"})
    assert r["dimensions"]["cost_limits"] is False
    assert r["qualified"] == "L1"  # no cost limit -> caps at L1


# --- runlog_wired_ids ---------------------------------------------------------

def test_runlog_wired_ids_scans_workflow(tmp_path):
    wf = tmp_path / "w.yml"
    wf.write_text("steps:\n  - run: python3 scripts/loop_runlog.py x\n")
    wired = la.runlog_wired_ids({"x": {"workflow": "w.yml"}, "y": {"workflow": "missing.yml"}},
                                workflows_dir=tmp_path)
    assert wired == {"x"}


# --- live registry invariant (mirrors CI --strict) ----------------------------

def test_live_registry_has_no_over_provisioned_loops():
    registry = yaml.safe_load((ROOT / "loops" / "registry.yaml").read_text())
    limits = yaml.safe_load((ROOT / "loops" / "limits.yaml").read_text())
    results = la.run_audit(registry, limits)
    over = [r["id"] for r in results if r["over_provisioned"]]
    assert over == [], f"over-provisioned loops: {over}"


def test_main_strict_exit_zero_on_live_registry():
    assert la.main(["--strict"]) == 0


def test_main_json_runs():
    assert la.main(["--json"]) == 0
