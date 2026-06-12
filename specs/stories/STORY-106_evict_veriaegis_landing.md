# STORY-106: Move `veriaegis-landing/` Out of the SARO Repo (G-6)
Status: ready
Screen/Area: Repo Structure / `veriaegis-landing/` (Next.js marketing site)

## Goal
A separate-brand marketing site lives inside the product repo and carries a `railway.toml` — a deployment config for the platform formally abandoned in ARCHITECTURE.md. This splits brand identity (VeriAegis vs SARO) inside the audited codebase and contradicts the canonical infrastructure-of-record. Relocate it to its own repository and purge the contradiction.

GRC mapping: ISO/IEC 42001 A.6.2.6 (configuration management); audit-scope minimization — every directory in the product repo is in scope for escrow and auditor review.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the landing site, When migration completes, Then it exists in its own repo (history preserved via subtree split or fresh init per owner's choice) and `veriaegis-landing/` is deleted from SARO.
- AC-2: Given the SARO repo post-merge, When searched, Then no `railway.toml` exists anywhere, and ARCHITECTURE.md remains the unchallenged infrastructure-of-record.
- AC-3: Given CI workflows, When inspected, Then no SARO workflow builds or references the landing site.
- AC-4: Given the landing site's content, When reviewed during migration, Then any compliance claims it makes are inventoried against the Claims Matrix (handoff to STORY-102 if contradictions found).

## Edge Cases
- Landing site sharing assets (logos, CSS tokens) with the React SPA → copy, don't symlink across repos.
- DNS/deploy config pointing at the monorepo path → re-point before deletion to avoid taking the marketing site down.

## Out of Scope
- Brand-consolidation decision (VeriAegis vs SARO naming) — product decision, separate track.

## Non-Functional Requirements
- Destructive action: confirm before deletion commit. Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
