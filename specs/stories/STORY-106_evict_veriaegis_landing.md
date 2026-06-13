# STORY-106: Evict the legacy "VeriAegis" landing site

**Status:** ready (⚠ destructive — removes the veriaegis-landing/ Next.js app)
**Screen/Area:** veriaegis-landing/ (standalone Next.js marketing site), .dockerignore, audit docs

## Goal
The repo carries a legacy `veriaegis-landing/` Next.js marketing site branded "SARO by Veriaegis" — a product name SARO no longer uses. It is not imported by the backend or referenced in CI. Remove the VeriAegis-branded landing site (and its stray references) so the repo carries no foreign-brand artifact.

## Decision Required (resolve at Definition-of-Ready)
- **Default: delete the whole `veriaegis-landing/` directory** and clean up references. The slug ("evict") implies removal.
- Alternative (only if the user says the marketing site is still needed): rebrand in place — replace every "Veriaegis"/"veriaegis.ai" with SARO equivalents instead of deleting. `/story` will confirm which before deleting.

## Context (file:line)
- `veriaegis-landing/package.json:2`, `veriaegis-landing/railway.toml:13` — name `veriaegis-landing`.
- `veriaegis-landing/app/layout.tsx:5,10,12,15,16,19,24` — "Veriaegis" in title/keywords/authors/OG/Twitter/url `https://veriaegis.ai`.
- `veriaegis-landing/app/components/Navbar.tsx:41`, `Footer.tsx:33` — "SARO by Veriaegis".
- `veriaegis-landing/app/components/CTABanner.tsx:42` — `mailto:hello@veriaegis.ai`.
- `veriaegis-landing/app/components/FAQ.tsx:9` — a copy of the "never calls external AI models" claim (coordinate with STORY-102).
- `.dockerignore` — multiple `veriaegis-landing/` paths (main + worktree mirrors).
- `docs/evf/evf_retrospective_audit_2026-06-02.json:238` — references the FAQ component path (historical audit record — do not rewrite history; see edge cases).

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given the default decision, When this story completes, Then the `veriaegis-landing/` directory is removed and a case-insensitive repo grep for `veriaegis` returns no hits in live source/config (excluding immutable historical audit JSON and `.claude/worktrees`).
- **AC-2:** Given `.dockerignore`, When inspected, Then stale `veriaegis-landing/` entries are removed (or left only as harmless ignore patterns that match nothing), with no dangling build reference.
- **AC-3:** Given the backend and CI, When `pytest tests/ -q` and the CI config are checked, Then nothing referenced the landing site and nothing breaks.
- **AC-4 (rebrand alt):** Given the rebrand alternative instead, Then every "Veriaegis"/`veriaegis.ai` token is replaced with the approved SARO brand/contact and the directory is renamed away from `veriaegis-landing`.

## Edge Cases
- `docs/evf/evf_retrospective_audit_2026-06-02.json` is an audit-evidence artifact; per compliance-guard, do not mutate historical audit records to erase a path reference — leave it as the historical fact it is.
- If `veriaegis-landing` has a live Railway/Vercel deployment, deleting source does not undeploy it — note as a follow-up; do not action infra without confirmation.

## Out of Scope
- Streamlit removal (STORY-105).
- Building a replacement SARO landing page.

## Non-Functional Requirements
- Follow `.claude/skills/compliance-guard` re: not rewriting audit history. Confirm delete-vs-rebrand before acting.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_veriaegis_landing_dir_removed`, `test_no_veriaegis_brand_in_live_source` | veriaegis-landing/ (removed) |
| AC-2 | `.dockerignore` is untracked (flyctl-generated, not in repo); its veriaegis patterns now match nothing | .dockerignore |
| AC-3 | unit + regression green; dir was imported by no backend/CI | tests/ |

**Status:** done (default: delete). Removed the `veriaegis-landing/` Next.js app (22 files) including the "SARO by Veriaegis" branding and `hello@veriaegis.ai`. Preserved `docs/evf/evf_retrospective_audit_2026-06-02.json` (audit history — not rewritten, per compliance-guard). `.dockerignore` left untouched (untracked local flyctl artifact; patterns harmlessly match nothing post-deletion). Branch `story/STORY-106_evict_veriaegis_landing` (stacked on 105).
