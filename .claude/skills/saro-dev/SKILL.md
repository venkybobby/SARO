---
name: saro-dev
description: Full SARO E2E implementation pipeline. Use when given requirements, specs, logs, debugging tasks, or any end-to-end feature request.
---

Run the full SARO engineering pipeline in strict order. Announce the current phase at the start of each step.

## Phase 1 — Requirements Analysis
- Identify affected files, routers, schemas, and scoring logic
- Clarify ambiguities before writing any code
- Flag any request that would violate SARO non-negotiables (see CLAUDE.md)

## Phase 2 — Plan & Confirm
- Produce a phased breakdown with file-level scope
- Ask for confirmation before proceeding to implementation
- Note any breaking changes and required migration path

## Phase 3 — Codebase Mapping
- Read all affected files before touching them
- Identify reuse opportunities — prefer editing over creating new files
- Check for existing tests covering the affected area

## Phase 4 — Incremental Implementation
- Write tests first (TDD) where practical
- Follow api-conventions skill for all new endpoints
- Follow risk-scoring skill for any engine.py changes
- Follow compliance-guard skill for audit/report changes
- Structured JSON logging with correlation IDs on all new code paths
- No external AI model calls in core scoring — the only exception is the optional, off-by-default Gate-3 LLM-judge (enabled only when its API key is set; see docs/COMPLIANCE_CLAIMS_MATRIX.md "External Model Usage")

## Phase 5 — Quality Gates (mandatory after every phase)
Run in order; do not skip:
1. `pytest tests/ -q --tb=short` — all must pass
2. Security: check for OWASP top-10 patterns in changed code
3. Compliance: verify no forbidden phrases per COMPLIANCE_CLAIMS_MATRIX.md
4. `git diff --stat` — confirm scope matches Phase 2 plan

## Phase 6 — Commit, Push, PR
- Conventional commit message with correct scope
- Push to active feature branch
- Create draft PR targeting venkybobby/SARO main

## Always enforce
- Clean modular architecture — no god functions
- No backwards-compat hacks for removed code
- No comments that explain WHAT; only WHY when non-obvious
- SARO never certifies compliance — evidence support only

End each phase with: **"Phase N complete. Next: [phase name]. Proceed?"**
