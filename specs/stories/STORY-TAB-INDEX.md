# STORY-TAB Index — /app tab contract fixes + consolidation

> Source: UI review of https://sarofrontend.fly.dev/app (2026-07-23) — seven tabs
> rendering improper values. TAB-001..007 are frontend/backend contract fixes
> (each independently shippable); TAB-008 is the nav consolidation and needs
> product sign-off before implementation.
>
> Status vocabulary is the closed set enforced by `scripts/check_story_index.py`:
> SPECIFIED (document exists, no code) → IMPLEMENTED (cites a reachable commit SHA) → MERGED.

| Story | Title | Status | Evidence |
|---|---|---|---|
| STORY-TAB-001 | Remediation tab response-contract fix (FND-073) | SPECIFIED | spec: specs/stories/STORY-TAB-001.md |
| STORY-TAB-002 | Onboarding tab renders backend checklist | SPECIFIED | spec: specs/stories/STORY-TAB-002.md |
| STORY-TAB-003 | Coverage Gap field alignment with coverage API | SPECIFIED | spec: specs/stories/STORY-TAB-003.md |
| STORY-TAB-004 | Evaluations RBAC / nav visibility alignment | SPECIFIED | spec: specs/stories/STORY-TAB-004.md |
| STORY-TAB-005 | Drift Alerts version grid from real response keys | SPECIFIED | spec: specs/stories/STORY-TAB-005.md |
| STORY-TAB-006 | Rule Packs detail fetch (rules actually display) | SPECIFIED | spec: specs/stories/STORY-TAB-006.md |
| STORY-TAB-007 | AIMS honest fields (no fabricated stage/tier) | SPECIFIED | spec: specs/stories/STORY-TAB-007.md |
| STORY-TAB-008 | Tab consolidation (7 → 2 top-level entries) | DRAFTED | spec: specs/stories/STORY-TAB-008.md — needs product sign-off; blocked on TAB-001..007 |
