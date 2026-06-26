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

## Remaining gaps

Not yet adopted from the reference toolkit: **`loop-cost`** token budgeting (the PR Babysitter
and CI Sweeper are the most expensive loops and currently uncapped) and **`loop-audit`**
readiness scoring for L1→L2→L3 promotion decisions.

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

## Maintenance

- Update `version` and `updated` in `loops/registry.yaml` on every change.
- When a `gap` loop is implemented, flip its `status` to `active` and point `implementation`
  at the real files.
- Cron cadences must match the actual `schedule:` in the corresponding workflow file.
