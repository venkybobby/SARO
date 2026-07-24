# STORY-TAB-002 — Onboarding renders the backend checklist

Stage: standard

## Lifecycle
- [x] discover   (skipped — endpoint + both consumers mapped this session; premise table in specs/stories/STORY-TAB-002.md)
- [x] shape      (interview skipped — autonomous session; decisions defaulted + logged below)
- [x] preview    (skipped — existing checklist layout retained; only data binding corrected)
- [x] plan
- [x] build      (implemented; gates green -- see PR)
- [x] verify     (batch change-debrief.html for STORY-TAB-001..007 -- committed on story/STORY-TAB-001, PR #128)
- [ ] sell       (n/a)

## Premise check (Stage 3a)

| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |
|---|---|---|
| `GET /api/v1/onboarding/status` → `{tenant_id, completed_steps, total_steps, completion_pct, onboarding_complete, steps:[{key,label,completed,cta_url}]}` (4 steps: profile, first_scan, aims_doc, sso) | yes | routers/onboarding.py:68-105; live probe 2026-07-23 |
| Onboarding tab hardcodes 7 divergent ids, flat-boolean reads | yes | frontend/src/pages/Onboarding.jsx:6-14,29 |
| SAME defect in AppShell's OnboardingWizard (first-login modal, same endpoint, 7 old ids + STEP_ACTIONS on old ids) | yes | frontend/src/components/AppShell.jsx:95-123 |
| No existing tests pin the wizard's onboarding behavior | yes | grep Onboarding in AppShell.test.jsx → no matches |
| Pages receive `onNavigate` from AppShell | yes | frontend/src/components/AppShell.jsx:271 |

## Decision Log

| Question | Answer (defaulted) | Architectural consequence |
|---|---|---|
| Wizard has the identical contract bug — fix here or separate story? | Fix both surfaces here. Same endpoint, same defect class (FND-075); fixing only the tab leaves the bug user-visible on every first login. | One shared steps-source module (`config/onboardingNav.js`) holding the step-key → in-app-page map; both consumers render API `steps` verbatim. |
| CTA mapping for backend keys (AC-4): which keys get in-app destinations? | Map only where the destination is unambiguous: `first_scan` → `upload`, `aims_doc` → `aims`. `profile`/`sso` render no link (no clearly-owned in-app page; API cta_urls are API paths, not navigable). | No dead links; unknown/future keys degrade to label-only rendering (data-driven). |
| Progress math | Always from API fields (`completion_pct`, `completed_steps`, `total_steps`) — never recomputed locally. | Single source of truth; empty `steps` can't divide-by-zero. |
| Error handling (tab currently fakes 0% on failure; wizard swallows) | Tab: explicit error banner (AC-5). Wizard: on fetch failure render nothing-harmful — keep modal with a neutral "couldn't load progress" line instead of a fake 0/7. | No fabricated progress claims on either surface. |

## Deviations
- Scope extends beyond the two files named in the story (adds AppShell.jsx wizard
  binding + shared config module) — same-defect-same-endpoint rationale above;
  conservative alternative (leave wizard broken) rejected as it ships a known
  false rendering. Logged as FND-075 alongside the tab fix.
