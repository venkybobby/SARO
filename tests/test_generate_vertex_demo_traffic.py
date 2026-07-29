"""Pins for the Vertex demo-traffic generator (scripts/generate_vertex_demo_traffic.py).

The scenario plan is deterministic by index, so these tests verify the exact
mix a live run would issue — without any GCP credentials or network. --dry-run
is proven to make no outbound call (socket.connect patched to fail).
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_vertex_demo_traffic import build_plan, main, plan_summary

pytestmark = pytest.mark.unit

REGIONS = ["us-central1", "europe-west4"]


def test_plan_has_exact_count_and_distribution():
    plan = build_plan(100, "gemini-2.0-flash", REGIONS)
    assert len(plan) == 100
    # Deterministic mix: 70 happy / 15 stream / 8 bad_model / 7 malformed.
    assert plan_summary(plan) == {
        "bad_model": 8,
        "happy": 70,
        "malformed": 7,
        "stream": 15,
    }


def test_error_scenarios_are_flagged_and_regions_cycle():
    plan = build_plan(100, "gemini-2.0-flash", REGIONS)
    for c in plan:
        assert c.region in REGIONS
        assert (c.category in ("bad_model", "malformed")) == c.expect_error
    # bad_model uses a nonexistent model id; streaming uses the stream method.
    assert any(
        c.model == "no-such-model-999" for c in plan if c.category == "bad_model"
    )
    assert all(
        c.method == "streamGenerateContent" for c in plan if c.category == "stream"
    )


def test_scales_to_other_counts():
    assert len(build_plan(250, "m", REGIONS)) == 250
    assert len(build_plan(1, "m", REGIONS)) == 1
    # single region is allowed
    plan = build_plan(10, "m", ["us-central1"])
    assert {c.region for c in plan} == {"us-central1"}


def test_dry_run_makes_no_network_call(monkeypatch, capsys):
    def _blocked(*a, **k):
        raise AssertionError("dry-run must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    rc = main(["--project", "demo-proj", "--count", "100", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "100 Vertex calls" in out
    assert "no calls issued" in out
