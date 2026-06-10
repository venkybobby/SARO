# SARO Engineering Standards

> Referenced by `/story` and `/finding` commands. **Prompts suggest, hooks enforce, CI guarantees** —
> nothing here relies on an agent's self-attestation; every gate is a command that must exit 0.

## Enforcement layers
| Layer | Mechanism | Bypassable by the model? |
|---|---|---|
| Suggest | CLAUDE.md, skills, this doc | yes |
| Enforce | `.claude/settings.json` hooks, `.pre-commit-config.yaml` | hard |
| Guarantee | `.github/workflows/ci.yml` + `quality-gates.yml` | no |

## Quality ratchet
- `quality/baseline.json` is seeded by `python scripts/update_quality_baseline.py` (manual, once, then on deliberate improvements).
- CI runs `scripts/check_quality_ratchet.py`: coverage may not drop (>0.5pt tolerance), ruff errors may not increase.
- Lowering the baseline requires a human-reviewed commit touching only `quality/baseline.json`.

## Findings ledger & regression aggregation
- Every review/incident finding → `FND-###` row in `quality/findings.md`.
- A finding is closed only when pinned by `tests/regression/test_fnd_###_*.py` + a `pinned` entry in `tests/regression/manifest.yaml`.
- The policy is machine-enforced by `tests/regression/test_manifest_integrity.py` (runs in CI): pinned entries must have files, files must have entries, quarantines expire in ≤14 days, no unapproved skips.
- Regression dir is append-only. Removal requires human approval recorded in the manifest.

## Test tiers
| Tier | When | Command |
|---|---|---|
| Fast | post-edit hook (auto) | `pytest tests/ -q --tb=short` (existing hook) |
| Standard | pre-commit | `pytest tests/ -m "unit" -q` + `pytest tests/regression -q` |
| Full | CI / phase close | full suite + coverage + ratchet + migrations-apply + e2e |
| Release | before Fly.io deploy | Full + post-deploy smoke: `/health` must return 200 from the deployed machine |

## Definition of Ready (gate 0 of /story)
A story file in `specs/stories/` must contain Given/When/Then acceptance criteria,
edge cases, and out-of-scope notes. Otherwise implementation does not start.

## Definition of Done (per story)
- [ ] All ACs mapped to passing tests (traceability table in the story file)
- [ ] Gates 1–7 of `/story` green with output shown
- [ ] Any bug touched → pinned regression test + manifest entry
- [ ] Ratchet holds
- [ ] Independent `reviewer` agent verdict: APPROVE (plus `security-auditor` PASS if auth/routers/middleware/rule_packs/migrations touched)
- [ ] Docs updated in the same change; migration path documented if a contract changed
- [ ] FILES CHANGED / NOT TOUCHED / CONCERNS summary delivered

## Hard rules
1. No gate passes without command output.
2. No bug fix without a regression test (red first).
3. Ratchet never goes backward.
4. Stop and ask on ambiguity — guessing is the #1 historical failure mode.
5. Never weaken, skip, or delete tests to achieve green. Max 3 full gate cycles, then write a blocker report.
6. One story = one branch (`story/STORY-###`) = one PR targeting `venkybobby/SARO`.

## Git workflow
- Branch from `main` per story; small commits at green states so any phase is revertible.
- Gates failing post-merge → revert first, diagnose second, log an FND third.
- Performance checks (Locust) are **advisory** locally — only CI-environment numbers count as a baseline.
