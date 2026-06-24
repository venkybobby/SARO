"""STORY-402 — Trigger Routing Layer tests.

AC coverage (see specs/stories/STORY-402.md):
- AC-1 block completes in budget → allow (integration, real timing)
- AC-2 block timeout + on_timeout=open → allow + flag async (integration)
- AC-3 block timeout + on_timeout=closed → block + route-to-human (integration)
- AC-4 per-request budget override is the effective budget (integration)
- AC-5 mirror returns before evaluation completes (integration, timing)
- AC-6 sample enqueues ~sample_rate fraction over N≥1000 (unit, seeded rng)
- AC-7 multi-policy: only block on critical path, rest enqueued; aggregate block (integration)
- AC-8 every dispatch emits a structured decision record (unit)

Invariant guard: deterministic dispatch — no external model/network call on any router path.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest

from models import Policy
from services import trigger_router


def _policy(trigger_mode: str, **kw) -> Policy:
    """Build an unpersisted Policy for routing (no DB needed)."""
    return Policy(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name=f"{trigger_mode}-p",
        trigger_mode=trigger_mode,
        policy_version=1,
        **kw,
    )


def _thread_enqueue(fn):
    threading.Thread(target=fn, daemon=True).start()


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3 — block path budget + timeout semantics
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_block_completes_in_budget_allows() -> None:
    p = _policy("block", latency_budget_ms=2000, on_timeout="closed")
    outcome = trigger_router.route_call([p], evaluate=lambda _p: "ok")
    d = outcome.decisions[0]
    assert outcome.allowed is True
    assert d.allowed is True and d.timed_out is False
    assert d.latency_ms is not None and d.fail_mode_applied is None


@pytest.mark.integration
def test_block_timeout_open_allows_and_flags() -> None:
    p = _policy("block", latency_budget_ms=50, on_timeout="open")
    outcome = trigger_router.route_call([p], evaluate=lambda _p: time.sleep(0.5))
    d = outcome.decisions[0]
    assert outcome.allowed is True
    assert d.timed_out is True and d.fail_mode_applied == "open"
    assert d.flagged_async is True


@pytest.mark.integration
def test_block_timeout_closed_blocks_and_routes_to_human() -> None:
    p = _policy("block", latency_budget_ms=50, on_timeout="closed")
    outcome = trigger_router.route_call([p], evaluate=lambda _p: time.sleep(0.5))
    d = outcome.decisions[0]
    assert outcome.allowed is False
    assert d.allowed is False and d.timed_out is True
    assert d.fail_mode_applied == "closed" and d.route_to_human is True


@pytest.mark.integration
def test_block_path_does_not_exceed_budget_plus_overhead() -> None:
    p = _policy("block", latency_budget_ms=100, on_timeout="open")
    start = time.monotonic()
    trigger_router.route_call([p], evaluate=lambda _p: time.sleep(2.0))
    elapsed_ms = (time.monotonic() - start) * 1000
    # Budget 100ms; allow generous fixed overhead but nowhere near the 2s eval.
    assert elapsed_ms < 800, (
        f"block path waited {elapsed_ms:.0f}ms, exceeding budget+overhead"
    )


# ---------------------------------------------------------------------------
# AC-4 — effective budget override
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_budget_override_is_effective_budget() -> None:
    # Policy budget would time out (50ms) on a 300ms eval; override to 2000ms rescues it.
    p = _policy("block", latency_budget_ms=50, on_timeout="closed")
    outcome = trigger_router.route_call(
        [p], evaluate=lambda _p: time.sleep(0.3), budget_override_ms=2000
    )
    assert outcome.allowed is True and outcome.decisions[0].timed_out is False


@pytest.mark.integration
def test_no_override_uses_policy_budget() -> None:
    p = _policy("block", latency_budget_ms=50, on_timeout="closed")
    outcome = trigger_router.route_call([p], evaluate=lambda _p: time.sleep(0.3))
    assert outcome.allowed is False and outcome.decisions[0].timed_out is True


@pytest.mark.unit
@pytest.mark.parametrize("bad", [0, -10])
def test_nonpositive_override_rejected(bad) -> None:
    p = _policy("block", latency_budget_ms=50, on_timeout="open")
    with pytest.raises(ValueError):
        trigger_router.route_call([p], evaluate=lambda _p: "x", budget_override_ms=bad)


@pytest.mark.integration
def test_block_evaluation_error_is_a_fail_not_a_hang() -> None:
    def boom(_p):
        raise RuntimeError("evaluator exploded with secret raw_output=PHI-12345")

    p = _policy("block", latency_budget_ms=2000, on_timeout="closed")
    outcome = trigger_router.route_call([p], evaluate=boom)
    d = outcome.decisions[0]
    assert outcome.allowed is False and d.error is not None
    # F2: the error field holds the exception TYPE only — never the message/content.
    assert d.error == "RuntimeError"
    assert "PHI-12345" not in (d.error or "") and "raw_output" not in (d.error or "")


@pytest.mark.integration
def test_block_evaluation_error_fail_open_allows() -> None:
    def boom(_p):
        raise ValueError("nope")

    p = _policy("block", latency_budget_ms=2000, on_timeout="open")
    outcome = trigger_router.route_call([p], evaluate=boom)
    d = outcome.decisions[0]
    assert outcome.allowed is True
    assert (
        d.fail_mode_applied == "open"
        and d.error == "ValueError"
        and d.flagged_async is True
    )


@pytest.mark.integration
def test_block_sheds_to_fail_mode_when_pool_saturated(monkeypatch) -> None:
    """F1 regression: when no worker slot frees within the budget, the block path sheds
    to its fail-mode within the budget instead of queueing behind abandoned threads."""
    # Shrink the slot pool to 1 and occupy it, so the next block call cannot acquire.
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(trigger_router, "_BLOCK_SLOTS", sem)
    assert sem.acquire(timeout=1) is True  # take the only slot

    p = _policy("block", latency_budget_ms=100, on_timeout="closed")
    start = time.monotonic()
    outcome = trigger_router.route_call([p], evaluate=lambda _p: "would-run")
    elapsed_ms = (time.monotonic() - start) * 1000

    d = outcome.decisions[0]
    assert outcome.allowed is False and d.timed_out is True
    assert "no capacity" in d.reason
    # Shed happened within ~budget, NOT by blocking indefinitely on a busy pool.
    assert elapsed_ms < 600, (
        f"saturated block path waited {elapsed_ms:.0f}ms (should shed at budget)"
    )
    sem.release()


# ---------------------------------------------------------------------------
# AC-5 — mirror is non-blocking
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mirror_returns_before_evaluation_completes() -> None:
    done = threading.Event()
    completed_at: list[float] = []

    def slow_eval(_p):
        time.sleep(0.3)
        completed_at.append(time.monotonic())
        done.set()

    p = _policy("mirror")
    t_return_before = time.monotonic()
    outcome = trigger_router.route_call(
        [p], evaluate=slow_eval, enqueue=_thread_enqueue
    )
    t_return = time.monotonic()

    assert outcome.allowed is True and outcome.decisions[0].enqueued is True
    assert not done.is_set(), "mirror blocked the caller until evaluation finished"
    assert done.wait(2.0), "enqueued evaluation never ran"
    assert completed_at[0] > t_return >= t_return_before


# ---------------------------------------------------------------------------
# AC-6 — sample rate over N calls
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("rate", [0.0, 0.3, 1.0])
def test_sample_fraction_within_tolerance(rate) -> None:
    import random

    rng = random.Random(20260624)
    enqueued = {"n": 0}

    def count_enqueue(_fn):
        enqueued["n"] += 1

    p = _policy("sample", sample_rate=rate)
    n = 2000
    for _ in range(n):
        out = trigger_router.route_call(
            [p], evaluate=lambda _p: None, enqueue=count_enqueue, rng=rng
        )
        assert out.allowed is True  # sample never blocks
    observed = enqueued["n"] / n
    assert abs(observed - rate) < 0.04, (
        f"sample fraction {observed:.3f} far from {rate}"
    )


# ---------------------------------------------------------------------------
# AC-7 — multi-policy split
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_multi_policy_only_block_on_critical_path() -> None:
    enq_calls = {"n": 0}

    def count_enqueue(_fn):
        enq_calls["n"] += 1

    policies = [
        _policy("block", latency_budget_ms=2000, on_timeout="closed"),
        _policy("mirror"),
        _policy("sample", sample_rate=1.0),
    ]
    outcome = trigger_router.route_call(
        policies, evaluate=lambda _p: "ok", enqueue=count_enqueue
    )
    assert outcome.allowed is True
    # mirror + sample(rate=1.0) both enqueued; block ran synchronously (not enqueued).
    assert enq_calls["n"] == 2
    modes = {d.trigger_mode: d for d in outcome.decisions}
    assert modes["block"].enqueued is False
    assert modes["mirror"].enqueued is True and modes["sample"].enqueued is True


@pytest.mark.integration
def test_aggregate_blocked_when_a_block_policy_blocks() -> None:
    policies = [
        _policy(
            "block", latency_budget_ms=50, on_timeout="closed"
        ),  # will time out → block
        _policy("mirror"),
    ]
    outcome = trigger_router.route_call(
        policies, evaluate=lambda _p: time.sleep(0.3), enqueue=lambda fn: None
    )
    assert outcome.allowed is False


# ---------------------------------------------------------------------------
# AC-8 — always emits a structured decision record
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_emits_decision_record_per_policy() -> None:
    emitted: list[trigger_router.RoutingDecision] = []
    policies = [_policy("mirror"), _policy("sample", sample_rate=1.0)]
    trigger_router.route_call(
        policies,
        evaluate=lambda _p: None,
        enqueue=lambda fn: None,
        emit=emitted.append,
    )
    assert len(emitted) == 2
    for d in emitted:
        assert d.policy_version == 1
        assert d.trigger_mode in {"mirror", "sample"}
        assert d.timestamp  # present
        assert d.decision in {"allow", "block"}


@pytest.mark.unit
def test_decision_record_carries_no_raw_content() -> None:
    """STORY-404 boundary: decision records hold identifiers/metadata, not raw IO."""
    from dataclasses import fields

    field_names = {f.name for f in fields(trigger_router.RoutingDecision)}
    for forbidden in ("prompt", "raw_output", "output", "input", "samples", "text"):
        assert forbidden not in field_names, (
            f"RoutingDecision must not carry {forbidden}"
        )


# ---------------------------------------------------------------------------
# Invariant guard — no network / external-model imports
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_network_or_model_calls_in_router() -> None:
    import inspect

    src = inspect.getsource(trigger_router)
    for needle in ("requests", "httpx", "urllib", "anthropic", "openai", "socket"):
        assert needle not in src, (
            f"trigger_router must not reference {needle} (Epic 14 invariant)"
        )
