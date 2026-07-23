# STORY-TAB-002: Onboarding tab — render the backend checklist instead of a divergent hardcoded one

**Status:** done
**Screen/Area:** Onboarding tab (frontend/src/pages/Onboarding.jsx ↔ routers/onboarding.py)

## Premise verification

| Referenced artifact | Evidence |
|---|---|
| `GET /api/v1/onboarding/status` returns `{steps: [{key, label, completed, cta_url}], completed_steps, total_steps, completion_pct, onboarding_complete}` with 4 steps | routers/onboarding.py:68-105 |
| Frontend hardcodes 7 different step ids and reads flat booleans (`progress[s.id]`) — never matches | frontend/src/pages/Onboarding.jsx:6-14,29 |
| Live deployment confirms shape and 4-step list | probed 2026-07-23 with demo token |

## Goal
The Onboarding tab always shows 0% with 7 permanently-unchecked steps because the page ignores the API's `steps` array and checks flat boolean keys that don't exist. After this story, the tab renders the backend's checklist verbatim — labels, completion state, and progress — so it reflects the tenant's real setup state.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the API returns its `steps` array, When the tab renders, Then exactly those steps are shown with their `label`, in API order, checked iff `completed` is true. The hardcoded ONBOARDING_STEPS list is removed.
- AC-2: Given the API response, Then the progress bar and "X/Y steps complete" derive from `completion_pct` / `completed_steps` / `total_steps` (not recomputed from a local list).
- AC-3: Given `onboarding_complete` is true, Then the completion banner is shown.
- AC-4: Given a step has a `cta_url` and is not completed, Then the step shows an affordance for it. API-path CTAs (`/api/v1/...`) are not user-navigable — map known step keys to in-app destinations (e.g. `first_scan` → Upload & Scan page) and render no link when no in-app mapping exists.
- AC-5: Given the API errors or returns non-2xx, Then the tab shows an error state instead of a fake 0% checklist.

## Edge Cases
- Empty `steps` array → neutral "no onboarding steps" message, no divide-by-zero (pct from API, not computed).
- Unknown future step keys → still render from `label` (rendering must be data-driven, not key-driven).

## Out of Scope
- Adding/changing backend steps or completion signals.
- Moving onboarding to a Dashboard first-run banner (STORY-TAB-008).

## Non-Functional Requirements
- Vitest contract-pin test using the exact backend response shape; must fail against the pre-fix component.
- Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `Onboarding.test.jsx`: "renders exactly the API's steps with their labels, checked iff completed" (old hardcoded labels asserted absent) | Onboarding.jsx, Onboarding.test.jsx |
| AC-2 | `Onboarding.test.jsx`: "AC-2: progress derives from API fields, not a local list" | Onboarding.jsx, Onboarding.test.jsx |
| AC-3 | `Onboarding.test.jsx`: "AC-3: onboarding_complete renders the completion banner" | Onboarding.jsx, Onboarding.test.jsx |
| AC-4 | `Onboarding.test.jsx`: "first_scan gets a Go button that navigates to upload; profile/sso get none" + "renders no raw /api/v1 hrefs" | Onboarding.jsx, config/onboardingNav.js, Onboarding.test.jsx |
| AC-5 | `Onboarding.test.jsx`: "non-2xx renders an error state, never a fake 0% checklist" | Onboarding.jsx, Onboarding.test.jsx |

**Edge cases covered:** empty `steps` → neutral message (no divide-by-zero — pct
is API-supplied); unknown future keys render from `label`. Both in `Onboarding.test.jsx`.

**Scope extension (logged deviation):** AppShell's `OnboardingWizard` (first-login
modal) had the identical contract bug against the same endpoint and is fixed in
the same change, sharing `config/onboardingNav.js`; pinned by three
"STORY-TAB-002 / FND-075" cases in `frontend/src/components/AppShell.test.jsx`.

**Finding:** FND-075 (quality/findings.md) — pinned red-first (11/14 failed
pre-fix across the two test files), manifest entry `status: pinned`.
