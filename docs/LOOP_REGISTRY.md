# SARO Loop Registry & Governance

> **Status:** v1.0 · Owner: Jordan Lee (Backend/Infra) · Reviewer: Venky (Lead) · 2026-06-26
> Machine-readable source of truth: [`loops/registry.yaml`](../loops/registry.yaml) (schema: [`loops/registry.schema.json`](../loops/registry.schema.json)).
> Validated in CI by `tests/test_loop_registry.py`.

## What this is

SARO already runs a substantial amount of **loop-engineered** automation — recurring,
self-driving agent processes with verification and human escalation built in. Until now
that automation was spread across `.github/workflows/`, `.claude/skills/`, and slash
commands with no single catalogue describing *which loop runs on what cadence, at what
risk, at what maturity*. This document and `loops/registry.yaml` are that catalogue.

The model is borrowed from the **loop-engineering** discipline
([github.com/cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering)):
*"You shouldn't be prompting coding agents anymore. You should be designing loops that
prompt your agents."* SARO is unusually well-suited to this because it already has the
hard parts — the **verification spine** that makes unattended automation safe.

## Why loops are safe to run in SARO (the verification spine)

Loops amplify both good and bad judgment; the risk is *unattended mistakes*. SARO mitigates
this with mechanisms most codebases lack:

| Mechanism | Where | What it guarantees |
|---|---|---|
| Quality ratchet | `quality/baseline.json` | A score that can't move backward |
| Regression manifest | `tests/regression/manifest.yaml` | Every fix pins a test; no silent regressions |
| Independent maker/checker | `reviewer` + `security-auditor` agents | Two fresh-context approvals before merge |
| Stop-hook gate | `.claude/settings.json` | Task can't complete unless full pytest passes |
| Rule-pack hard gate | PreToolUse Write hook | `rule_packs/` writes require explicit human approval |
| Compliance matrix | `docs/COMPLIANCE_CLAIMS_MATRIX.md` | Hard boundary against overclaiming |
| Escalation rule | `docs/engineering-standards.md` | Max 3 gate cycles, then human; never weaken a test |

**These are the brakes. They are exactly what make the throttle safe to install.**

## The maturity ladder

Every loop has a current `maturity` and a `max_maturity` cap it may never exceed
(enforced by `tests/test_loop_registry.py`).

- **L1 — Report-only.** The loop discovers and proposes; a human makes every change. Safe default.
- **L2 — Assisted.** The loop may push fixes on a branch/PR; a human reviews and merges.
- **L3 — Unattended.** The loop acts end-to-end within hard guardrails (tests, ratchet, escalation).

**Governing principle — loop the toil, gate the judgment.** Loops over mechanical toil
(CI, PRs, deps, changelogs) may climb to L3. Loops touching SARO's *product correctness or
legal posture* — scoring math (`engine.py`), `rule_packs/`, compliance copy — are
**permanently capped at L1**. The cost of an unattended mistake there is regulatory and
reputational, not a red CI run. This cap is encoded in the registry and asserted by tests.

## The catalogue (summary)

Full detail in `loops/registry.yaml`. Loops mapped to the seven loop-engineering reference
patterns plus SARO-native categories:

| Loop | Category | Trigger | Cadence | Risk | Maturity | Cap |
|---|---|---|---|---|---|---|
| PR Babysitter | pr-babysitter | PR event | on event | medium | L3 | L3 |
| CI Sweeper | ci-sweeper | PR | on CI failure | medium | L3 | L3 |
| Finding Intake | issue-triage | manual | per finding | low | L2 | L2 |
| Story Pipeline | dev-pipeline | manual | per story | medium | L2 | L2 |
| Security Sweeper | evidence-generator | schedule | Mon 02:00 UTC | medium | L1 | L2 |
| Offline Eval Batch | evidence-generator | schedule | Mon 02:00 UTC | low | L1 | L1 |
| Security Evidence | evidence-generator | schedule | Mon 03:00 UTC | low | L1 | L1 |
| HF Daily Sampler | data-refresh | schedule | 06:00 UTC daily | low | L1 | L1 |
| Seed Refresh | data-refresh | schedule | Sun 02:00 UTC | low | L1 | L1 |
| Compliance Guard | guard-skill | agent-context | on edit | high | L1 | **L1** |
| Risk Scoring Guard | guard-skill | agent-context | on edit | high | L1 | **L1** |
| Rule Pack Guard | guard-skill | agent-context | on edit | high | L1 | **L1** |
| Drift Sentinel | guard-skill | agent-context | on edit | high | L1 | **L1** |
| Verification Loop | guard-skill | agent-context | pre-commit | low | L1 | L2 |
| Dependency Sweeper | dependency-sweeper | schedule | Mon 04:17 UTC | medium | L2 | L2 |
| Changelog Drafter | changelog-drafter | tag push | on `v*` tag | low | L2 | L2 |
| Post-Merge Cleanup | post-merge-cleanup | schedule | 05:23 UTC daily | low | L1 | L2 |

## Adopted maintenance loops (deterministic, no LLM cost)

Three reference patterns from loop-engineering are now implemented as deterministic,
unit-tested Python scripts driven by GitHub Actions — cheap, predictable, and PR/dry-run safe:

1. **Dependency Sweeper** (`scripts/dependency_sweeper.py`) — weekly, patch-only. Bumps exact
   `name==X.Y.Z` pins to the latest patch within the same major.minor, runs the full suite, and
   opens a **draft PR**. Never bumps minor/major, never touches `>=` floors, never auto-merges.
2. **Changelog Drafter** (`scripts/changelog_drafter.py`) — on `v*` tag push (or manual). Groups
   Conventional Commits by type (with a BREAKING CHANGES section) and opens a **draft PR** updating
   `CHANGELOG.md`. Never tags or publishes a release.
3. **Post-Merge Cleanup** (`scripts/post_merge_cleanup.py`) — daily, off-peak. **Dry-run by
   default** (logs candidates only); deletion of git-confirmed merged branches requires an explicit
   operator dispatch. Protected globs (`main`/`develop`, `automation/*`, `claude/*`) are never touched.

Each ships unit tests for its pure logic (`tests/test_dependency_sweeper.py`,
`tests/test_changelog_drafter.py`, `tests/test_post_merge_cleanup.py`).

## Cost & Limits / Kill Switch

Every workflow-driven loop runs a **preflight `guard` job** (`scripts/loop_guard.py`) before
doing any work, gated by `needs: guard` + `if: needs.guard.outputs.proceed == 'true'`. A halted
run is **green and does nothing** — it is not a failure, so the kill switch never pages anyone.
Limits live in [`loops/limits.yaml`](../loops/limits.yaml).

The guard enforces three controls, cheapest first:

| Control | Where | Effect |
|---|---|---|
| **Global kill switch** | `kill_switch: true` in `limits.yaml`, or env `SARO_LOOPS_KILL_SWITCH=1` | Halts **every** loop at preflight. The env var wins, so an operator can stop the whole fleet without waiting on a merge. |
| **Per-loop enable** | `loops.<id>.enabled: false` | Halts one loop. |
| **Daily run cap** | `loops.<id>.daily_run_cap` | Halts once the loop's workflow has run N times today (UTC), counted via the Actions API. Per-run cost × cap is the spend envelope; token budgets in `limits.yaml` document the intended ceiling. |

**Operator runbook (stop a runaway loop):**
1. *Right now, no commit* — set repo/Actions variable `SARO_LOOPS_KILL_SWITCH=1`.
2. *Auditable* — set `kill_switch: true` in `limits.yaml` and merge (the off switch is then in git history — useful for a compliance product).
3. *One loop only* — set that loop's `enabled: false` and merge.

`tests/test_loop_guard.py` enforces the decision logic and keeps `limits.yaml` ids in sync with
the registry and with real workflow files.

## Readiness audit (`loop-audit`)

`scripts/loop_audit.py` scores every loop against the design-checklist dimensions (purpose,
scheduling, implementation, human handoff, verification, maker/checker, cost limits,
observability), derives the **maturity its evidence justifies**, and flags any loop whose
declared maturity exceeds it ("over-provisioned" — loop-engineering anti-pattern #4, *L3 before
L1 quality*). Dimensions that don't apply to a loop type (e.g. cost limits for a contextual
guard skill) are not held against it.

It runs in CI with `--strict` (in `quality-gates.yml`), so a loop can never be promoted past its
evidence — the audit fails the build. `tests/test_loop_audit.py` pins the same invariant. Run
`python scripts/loop_audit.py` locally for the readiness report, `--json` for machine output.

## Observability run-log

`scripts/loop_runlog.py` records a structured entry per loop run, anti-pattern #10 (*no run
log*). Two sinks:

- **GitHub Actions job summary** — every workflow loop writes a per-run row (zero commit noise),
  giving live observability even for the high-frequency LLM loops.
- **`loops/run-log.md`** — a committed, auditable ledger. The low-frequency, PR-action-free
  Post-Merge Cleanup appends + commits an entry per run (`[skip ci]`, mirroring the weekly
  security-evidence pattern), so a durable history lives in git for the compliance audit trail.

The audit's *observability* dimension is satisfied when a loop's workflow records via
`loop_runlog.py`.

## Remaining gaps

Token budgets in `limits.yaml` are declared ceilings enforced via the run cap rather than
**measured** spend; metering actual tokens per run (instrumenting the Claude action's usage) is
the last open item from the reference toolkit.

## Governance rules

1. **The registry is the source of truth.** Any new automated loop (workflow, skill, or
   subscription) must be added to `loops/registry.yaml` in the same PR that introduces it.
2. **Promotion is deliberate.** Moving a loop up the ladder (e.g. L1→L2) is a reviewed change
   to its `maturity` field, justified in the PR. It may never exceed `max_maturity`.
3. **Judgment loops stay at L1.** Loops over scoring, compliance, and rule-packs are capped at
   L1 by policy and by test. Lifting that cap is out of scope for any normal PR.
4. **Every loop declares its escalation path.** No loop is unattended without a documented
   human handoff.
5. **The test guards the rules.** `tests/test_loop_registry.py` enforces schema conformance,
   unique ids, real owners, the maturity cap, and the judgment-loop L1 cap. It runs in the
   standard pytest gate.
6. **Every workflow-driven loop is behind the guard.** A new scheduled or event-driven loop must
   add a `guard` job calling `scripts/loop_guard.py <id>` and an entry in `loops/limits.yaml`
   (kept in sync by `tests/test_loop_guard.py`). No loop ships without a kill switch.
7. **No loop above its evidence.** `scripts/loop_audit.py --strict` runs in CI; a loop's declared
   maturity may not exceed the level its checklist evidence justifies. Raising a maturity means
   adding the evidence (verification, limits, observability, independent review), not the number.

## Maintenance

- Update `version` and `updated` in `loops/registry.yaml` on every change.
- When a `gap` loop is implemented, flip its `status` to `active` and point `implementation`
  at the real files.
- Cron cadences must match the actual `schedule:` in the corresponding workflow file.
