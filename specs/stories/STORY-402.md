# STORY-402: Trigger Routing Layer

**Status:** done
**Screen/Area:** Governance Runtime — dispatch (Epic 14, Phase 1)
**Depends on:** STORY-401 (Policy schema). Stacked on `story/STORY-401` until it merges.

## Goal
Read a policy's trigger config and dispatch evaluation accordingly — this is where
"near real-time" is honored. A deterministic router that runs `block` policies
synchronously within a latency budget (applying `on_timeout` semantics), enqueues
`mirror` policies without blocking, and probabilistically enqueues `sample` policies.
A single call may match multiple policies across modes: only `block` runs on the
critical path; the rest are enqueued. Every dispatch emits a structured decision
record to the audit path (the STORY-404 contract), even when allowing.

The router dispatches into an **injected evaluation callable** (the `engine.run_audit`
seam per STORY-400) and an **injected enqueue callable** (FastAPI `BackgroundTasks`
in production per STORY-400; a fake in tests) — it never hard-wires either, so it
stays deterministic and unit-testable.

## Acceptance Criteria (Given/When/Then)

- **AC-1 (block in budget):** Given a `block` policy with `latency_budget_ms=B`, When the
  evaluation completes within the effective budget, Then the call is allowed, the decision
  record carries the measured latency and `timed_out=False`.

- **AC-2 (block timeout → open):** Given a `block` policy with `on_timeout=open`, When the
  evaluation exceeds the effective budget, Then the router allows the call, flags it for
  async follow-up, and records `fail_mode_applied=open`, `timed_out=True`.

- **AC-3 (block timeout → closed):** Given a `block` policy with `on_timeout=closed`, When the
  evaluation exceeds the effective budget, Then the router blocks the call, signals
  route-to-human, and records `fail_mode_applied=closed`, `timed_out=True`.

- **AC-4 (effective budget override):** Given a per-request budget override is supplied, When a
  `block` policy is routed, Then the override is the effective budget (not the policy's
  `latency_budget_ms`); with no override the policy value is used. (The override is a
  parameter supplied by the caller — surface logic is out of scope.)

- **AC-5 (mirror non-blocking):** Given a `mirror` policy, When routed, Then the router enqueues
  the evaluation and returns control **before** evaluation completes (caller-return timestamp
  precedes evaluation-complete timestamp), and the call is allowed.

- **AC-6 (sample rate):** Given a `sample` policy with `sample_rate=r`, When routed over N≥1000
  calls, Then the enqueued fraction is within tolerance of `r`; each call returns immediately
  and is allowed.

- **AC-7 (multi-policy split):** Given one call matching several policies across modes, When
  routed, Then only the `block` policies run on the critical path and the `mirror`/`sample`
  policies are enqueued; the aggregate is blocked iff some `block` policy blocked.

- **AC-8 (always emits):** Given any dispatch outcome (allow, block, timeout, enqueue), When the
  router runs, Then a structured decision record is emitted via the injected emit interface —
  including `policy_version`, `trigger_mode`, decision, reason, latency, and fail-mode applied.

## Edge Cases
- Effective budget from override of 0/negative is rejected (caller error), not silently ignored.
- A `block` evaluation that raises is treated as a fail (not a hang); decision records the error.
- `sample_rate=0.0` enqueues nothing; `1.0` enqueues every call.
- Enqueue/emit callables default to safe no-ops so the router is usable without wiring.

## Out of Scope
- Member-facing vs internal surface budget assignment (Open #2 — workshop-dependent). The router
  only exposes the override **parameter**; the value's origin is the caller's concern.
- Provider taps / action-axis mediation (held).
- The real audit emitter + hash chaining (STORY-404 implements the emit interface).
- A durable queue: Phase-1 substrate is BackgroundTasks / a thread pool; 500/s durable queue is
  the Phase-2 upgrade flagged in STORY-400 (recorded, not built).
- HTTP endpoint wiring (the router is a dispatch service; a thin endpoint can come later).

## Non-Functional Requirements
- **Invariant guard (Epic 14):** deterministic dispatch — **no external model/network call** on
  any router path; the only model interaction is through the caller-injected evaluate callable.
- `mirror`/`sample` must not block the caller; `block` must not exceed effective budget + a small
  fixed overhead (timing-asserted).
- Decision records carry no raw input/output content (STORY-404 boundary) — identifiers/metadata only.
- Anti-overclaim (ADR-004): decision records describe what was measured/decided, no guarantees.

## Traceability
All tests in `tests/test_story402_trigger_router.py`; implementation in `services/trigger_router.py`.

| AC | Test(s) | Files |
|---|---|---|
| AC-1 block in budget | `test_block_completes_in_budget_allows` | services/trigger_router.py |
| AC-2 timeout→open | `test_block_timeout_open_allows_and_flags` | services/trigger_router.py |
| AC-3 timeout→closed | `test_block_timeout_closed_blocks_and_routes_to_human` | services/trigger_router.py |
| AC-4 budget override | `test_budget_override_is_effective_budget`, `test_no_override_uses_policy_budget`, `test_nonpositive_override_rejected` | services/trigger_router.py |
| AC-5 mirror non-blocking | `test_mirror_returns_before_evaluation_completes` | services/trigger_router.py |
| AC-6 sample rate | `test_sample_fraction_within_tolerance` | services/trigger_router.py |
| AC-7 multi-policy split | `test_multi_policy_only_block_on_critical_path`, `test_aggregate_blocked_when_a_block_policy_blocks` | services/trigger_router.py |
| AC-8 always emits | `test_emits_decision_record_per_policy`, `test_decision_record_carries_no_raw_content` | services/trigger_router.py |
| Edge: budget bound | `test_block_path_does_not_exceed_budget_plus_overhead` | services/trigger_router.py |
| Edge: eval error | `test_block_evaluation_error_is_a_fail_not_a_hang`, `test_block_evaluation_error_fail_open_allows` | services/trigger_router.py |
| Review F1: shed-load | `test_block_sheds_to_fail_mode_when_pool_saturated` | services/trigger_router.py |
| Review F2: no content leak | `test_block_evaluation_error_is_a_fail_not_a_hang` (asserts type-name only) | services/trigger_router.py |
| Invariant | `test_no_network_or_model_calls_in_router` | services/trigger_router.py |
