---
description: Execute a SARO story end-to-end through the full quality loop
argument-hint: <STORY-ID> (must exist as specs/stories/<STORY-ID>.md)
---

Execute story **$ARGUMENTS** through the SARO engineering loop. Full standards:
@docs/engineering-standards.md — this command is the operational checklist.

## 0. Definition of Ready (hard gate — stop if it fails)
Read `specs/stories/$ARGUMENTS.md`. It must contain: acceptance criteria in
Given/When/Then, edge cases, and out-of-scope notes. If anything is missing or
ambiguous: STOP, list the gaps as questions, and wait. Do not guess.

## 1. Analyze
- Extract ACs, edge cases, NFRs. State assumptions explicitly:
  `ASSUMPTIONS I'M MAKING: ... → Correct me now or I proceed.`
- Check `quality/findings.md` for prior findings touching the same files —
  any `verify-pinned` finding in scope gets its regression test written FIRST.

## 2. Plan
Emit a numbered plan where **every step names its verification command**.
Wait for confirmation before implementing.

## 3. Implement (TDD — use the tdd-enforcer skill)
- Red → Green → Refactor, one AC at a time. Smallest change that passes.
- Scope discipline: touch only files named in the plan. No drive-by refactors.

## 4. Gates (run each, show output; all must exit 0)
1. `ruff check . && ruff format --check .`
2. `mypy . --ignore-missing-imports`
3. `pytest tests/ -m unit -q`
4. `pytest tests/ -m integration -q`
5. `pytest tests/regression -q`  ← full, never sampled
6. `python scripts/check_quality_ratchet.py` (after `pytest --cov=. --cov-report=json -q`)
7. `bandit -r . -ll -x ./tests,./saro-data-framework`
After any fix, rerun ALL gates. Max 3 full cycles, then stop and write a
blocker report — never weaken or skip a test to get green.

## 5. Independent review (fresh context)
Invoke the `reviewer` agent on the diff, and the `security-auditor` agent if the
story touches auth.py, routers/, middleware/, or rule_packs/. Address findings
or log them as FND entries in `quality/findings.md`.

## 6. Close
- Bug touched? → regression test in `tests/regression/` + manifest entry, status `pinned`.
- Update docs touched by the change, and the story file's traceability section
  (AC → test IDs → files).
- Definition of Done check, then end with:
  FILES CHANGED / FILES NOT TOUCHED / CONCERNS / NEXT STEPS.
- Commit on branch `story/$ARGUMENTS`; confirm before pushing or opening a PR
  (target `venkybobby/SARO`, never saro-platform).
