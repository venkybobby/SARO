"""STORY-402 (Epic 14): trigger routing layer.

Reads a policy's trigger config (STORY-401) and dispatches evaluation accordingly —
this is where "near real-time" is honored:

  block  — run synchronously within an effective latency budget; on timeout apply
           on_timeout ('open' → allow + flag-async; 'closed' → block + route-to-human).
  mirror — enqueue and return immediately (never blocks the caller).
  sample — enqueue for sample_rate fraction of calls; return immediately.

A single call may match several policies across modes: only `block` policies run on
the critical path; `mirror`/`sample` are enqueued. Every dispatch emits a structured
RoutingDecision (the STORY-404 audit contract) — even when allowing.

The router dispatches into an INJECTED evaluation callable (the engine.run_audit seam
per STORY-400) and an INJECTED enqueue callable (FastAPI BackgroundTasks in production;
a fake in tests). It never hard-wires either, so it stays deterministic and testable.

Invariant guard (Epic 14): deterministic dispatch — NO external model/network call on
any path here; the only model interaction is through the caller-supplied `evaluate`.
RoutingDecision carries identifiers/metadata only, never raw input/output (STORY-404).

Phase-1 substrate note: block evaluation and async (mirror/sample) work run on two
SEPARATE bounded thread pools, and the block path holds a worker-slot semaphore so it
sheds to its fail-mode within budget when saturated instead of queueing behind
abandoned (timed-out-but-still-running) threads. A durable queue + true cancellation
for sustained 500/s bursty peak is the Phase-2 upgrade recorded in the STORY-400 recon
findings, not built here.
"""

from __future__ import annotations

import os
import random
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from models import Policy

EvaluateFn = Callable[[Policy], Any]
EnqueueFn = Callable[[Callable[[], Any]], None]
EmitFn = Callable[["RoutingDecision"], None]

# Two SEPARATE bounded pools so the critical block path is never starved by the
# fire-and-forget async work (mirror/sample/drain) — the shared-pool coupling a
# review flagged. `_BLOCK_SLOTS` tracks real worker occupancy: a slot is held for
# the whole lifetime of an evaluation (including a timed-out-but-still-running one,
# which cannot be force-cancelled) and released by the future's done-callback. When
# no slot frees within the budget, the block path SHEDS to its fail-mode instead of
# queueing behind abandoned threads — so the budget always bounds caller wait time.
# Phase-1: a durable queue + true cancellation for sustained 500/s is the Phase-2
# upgrade recorded in the STORY-400 recon findings, not built here.
_MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)
_BLOCK_EXECUTOR = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS, thread_name_prefix="saro-block"
)
_ENQUEUE_EXECUTOR = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS, thread_name_prefix="saro-enqueue"
)
_BLOCK_SLOTS = threading.BoundedSemaphore(_MAX_WORKERS)
_RNG = random.Random()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RoutingDecision:
    """Structured, content-free record of a single policy's dispatch outcome.

    Identifiers + metadata only (no prompt/raw_output) — the STORY-404 emitter
    consumes this and adds hashes/chaining.
    """

    policy_id: str
    policy_version: int
    trigger_mode: str
    decision: str  # "allow" | "block"
    allowed: bool
    reason: str
    enqueued: bool = False
    latency_ms: float | None = None
    timed_out: bool = False
    fail_mode_applied: str | None = None  # "open" | "closed" | None
    flagged_async: bool = False
    route_to_human: bool = False
    error: str | None = None
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class RoutingOutcome:
    """Aggregate result of routing one call across all matched policies."""

    allowed: bool
    decisions: list[RoutingDecision]


def _noop_emit(_decision: RoutingDecision) -> None:
    """Default audit sink — replaced by the STORY-404 emitter in production."""


def _default_enqueue(fn: Callable[[], Any]) -> None:
    """Fire-and-forget async substrate (Phase-1 thread pool, separate from block)."""
    _ENQUEUE_EXECUTOR.submit(fn)


def effective_budget_ms(policy: Policy, budget_override_ms: int | None) -> int:
    """The budget actually applied: per-request override if supplied, else the policy's.

    A supplied override must be positive — a 0/negative override is a caller error,
    not a silent fall-through to the policy value (which would mask misconfig).
    """
    if budget_override_ms is not None:
        if budget_override_ms <= 0:
            raise ValueError("budget_override_ms must be > 0")
        return budget_override_ms
    if policy.latency_budget_ms is None or policy.latency_budget_ms <= 0:
        raise ValueError(f"block policy {policy.id} has no positive latency_budget_ms")
    return policy.latency_budget_ms


def _new_decision(policy: Policy, **kw: Any) -> RoutingDecision:
    return RoutingDecision(
        policy_id=str(policy.id),
        policy_version=policy.policy_version,
        trigger_mode=policy.trigger_mode,
        **kw,
    )


def _fail_mode_decision(
    policy: Policy,
    latency_ms: float,
    *,
    reason_kind: str,
    timed_out: bool,
    error: str | None = None,
) -> RoutingDecision:
    """Build the decision for a block policy that did not cleanly complete.

    fail-open (on_timeout='open') → allow + flag-async; anything else (closed, or a
    null/unknown value) fails SAFE to closed → block + route-to-human. Fail-open is
    thus never a silent default — it requires the explicit 'open' config.
    """
    if policy.on_timeout == "open":
        return _new_decision(
            policy,
            decision="allow",
            allowed=True,
            reason=f"block: {reason_kind}, fail-open",
            latency_ms=latency_ms,
            timed_out=timed_out,
            fail_mode_applied="open",
            flagged_async=True,
            error=error,
        )
    return _new_decision(
        policy,
        decision="block",
        allowed=False,
        reason=f"block: {reason_kind}, fail-closed",
        latency_ms=latency_ms,
        timed_out=timed_out,
        fail_mode_applied="closed",
        route_to_human=True,
        error=error,
    )


def _release_slot_and_drain(future: Future) -> None:
    """Done-callback: retrieve the future's exception (so it's never unobserved) and
    release the worker slot — fires when the evaluation TRULY finishes, even if the
    caller already stopped waiting on a timeout (so the slot reflects real occupancy)."""
    try:
        future.exception()
    except Exception:  # noqa: BLE001 — async tail; nothing to propagate to the caller
        pass
    finally:
        _BLOCK_SLOTS.release()


def _run_block(
    policy: Policy,
    evaluate: EvaluateFn,
    budget_override_ms: int | None,
) -> RoutingDecision:
    budget_s = effective_budget_ms(policy, budget_override_ms) / 1000.0
    start = time.monotonic()
    # Acquire a worker slot within the budget. If none frees in time, the pool is
    # saturated — shed to the fail-mode rather than queueing behind abandoned threads,
    # so caller wait stays bounded by the budget.
    if not _BLOCK_SLOTS.acquire(timeout=budget_s):
        latency_ms = (time.monotonic() - start) * 1000
        return _fail_mode_decision(
            policy, latency_ms, reason_kind="no capacity within budget", timed_out=True
        )
    try:
        future: Future = _BLOCK_EXECUTOR.submit(evaluate, policy)
    except Exception:  # noqa: BLE001 — submit failed (pool shutdown / OOM); we still hold the slot
        _BLOCK_SLOTS.release()
        latency_ms = (time.monotonic() - start) * 1000
        return _fail_mode_decision(
            policy, latency_ms, reason_kind="no capacity within budget", timed_out=True
        )
    future.add_done_callback(_release_slot_and_drain)
    remaining_s = max(0.0, budget_s - (time.monotonic() - start))
    try:
        future.result(timeout=remaining_s)
    except FutureTimeoutError:
        latency_ms = (time.monotonic() - start) * 1000
        return _fail_mode_decision(
            policy, latency_ms, reason_kind="budget exceeded", timed_out=True
        )
    except Exception as exc:  # noqa: BLE001 — an evaluator failure must not crash the router
        # An evaluation error is a fail (not a hang). Record only the exception TYPE,
        # never repr(exc), so caller-supplied content can't leak into the audit record.
        latency_ms = (time.monotonic() - start) * 1000
        return _fail_mode_decision(
            policy,
            latency_ms,
            reason_kind="evaluation error",
            timed_out=False,
            error=type(exc).__name__,
        )
    latency_ms = (time.monotonic() - start) * 1000
    return _new_decision(
        policy,
        decision="allow",
        allowed=True,
        reason="block: completed in budget",
        latency_ms=latency_ms,
        timed_out=False,
    )


def _dispatch_mirror(
    policy: Policy, evaluate: EvaluateFn, enqueue: EnqueueFn
) -> RoutingDecision:
    enqueue(lambda: evaluate(policy))
    return _new_decision(
        policy,
        decision="allow",
        allowed=True,
        reason="mirror: enqueued (non-blocking)",
        enqueued=True,
    )


def _dispatch_sample(
    policy: Policy, evaluate: EvaluateFn, enqueue: EnqueueFn, rng: random.Random
) -> RoutingDecision:
    rate = policy.sample_rate if policy.sample_rate is not None else 0.0
    sampled = rng.random() < rate
    if sampled:
        enqueue(lambda: evaluate(policy))
    return _new_decision(
        policy,
        decision="allow",
        allowed=True,
        reason="sample: enqueued" if sampled else "sample: skipped",
        enqueued=sampled,
    )


def route_call(
    policies: Sequence[Policy],
    evaluate: EvaluateFn,
    *,
    budget_override_ms: int | None = None,
    enqueue: EnqueueFn | None = None,
    emit: EmitFn | None = None,
    rng: random.Random | None = None,
) -> RoutingOutcome:
    """Dispatch one call across all matched policies.

    block policies run synchronously on the critical path (honoring the effective
    budget + on_timeout); mirror/sample are enqueued. The aggregate is blocked iff
    some block policy blocked. A RoutingDecision is emitted for every policy.
    """
    enqueue = enqueue or _default_enqueue
    emit = emit or _noop_emit
    rng = rng or _RNG

    block_policies = [p for p in policies if p.trigger_mode == "block"]
    other_policies = [p for p in policies if p.trigger_mode != "block"]

    decisions: list[RoutingDecision] = []
    aggregate_allowed = True

    # Critical path first: only block policies.
    for policy in block_policies:
        decision = _run_block(policy, evaluate, budget_override_ms)
        decisions.append(decision)
        emit(decision)
        if not decision.allowed:
            aggregate_allowed = False

    # Everything else is enqueued (non-blocking).
    for policy in other_policies:
        if policy.trigger_mode == "mirror":
            decision = _dispatch_mirror(policy, evaluate, enqueue)
        elif policy.trigger_mode == "sample":
            decision = _dispatch_sample(policy, evaluate, enqueue, rng)
        else:  # pragma: no cover — schema CHECK constrains trigger_mode
            raise ValueError(f"unknown trigger_mode {policy.trigger_mode!r}")
        decisions.append(decision)
        emit(decision)

    return RoutingOutcome(allowed=aggregate_allowed, decisions=decisions)
