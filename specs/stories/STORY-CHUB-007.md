STORY-CHUB-007: Compliance Hub — refactor onto the shared design system
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P2 · Depends on: —

Goal
`ComplianceHub.jsx` is visually disconnected from the rest of the app: it uses hardcoded hex colors (`#fff`, `#0d9488`, …), `fontFamily: "system-ui"`, emoji headers (🏛️ 📅), and its own local `Card`/`api` helpers, while `Dashboard.jsx` and peers use the design-token system and shared components (`PageHeader`, `Card`, `Badge`, `Skeleton`, `EmptyState` from `components/ui/index.jsx`). Refactor for visual and structural consistency without changing behavior.

Framework mapping (per ADR-004 scope locks)
- No new compliance claims; presentation refactor only. Wording must remain scope-lock compliant.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `frontend/src/pages/ComplianceHub.jsx`, When refactored, Then it renders a shared `PageHeader` (title "Compliance Hub", persona subtitle) matching the Dashboard pattern, with no emoji in headings.
AC-2: Given all color and spacing values, When refactored, Then they use design tokens (`var(--color-*)`, `var(--space-*)`, `var(--radius-*)`, `var(--font-*)`) — no hardcoded hex or `system-ui` literals remain in the file.
AC-3: Given the local `Card`/`api` helpers, When refactored, Then the screen uses the shared `Card` and the project's standard fetch/auth utility (consolidating the duplicate helper).
AC-4: Given the refactor, When the page renders, Then all existing data, sections, and behavior are unchanged (pure presentation refactor) — verified by snapshot/behavioral tests.

Edge Cases
- The `TierBadge`/`RiskBadge` color logic must move to tokens without changing the displayed colors materially (RED ≥70, AMBER ≥40, GREEN otherwise).
- The disclaimer footer wording is preserved verbatim (legal text).

Out of Scope
- Behavioral fixes (covered by CHUB-001..006); this is presentation only.
- Building new shared components — reuse existing ones.

Non-Functional Requirements
- No net change in rendered data; diff is style/structure only.
- File passes `pre-edit-standards-check.sh` (no scope overreach introduced).

Test Requirements
- Frontend unit (`ComplianceHub.test.jsx`): renders `PageHeader`; assert no `#`-hex literals and no `system-ui` in the rendered style props (lint/string check); existing section tests still pass unchanged.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	ComplianceHub.test.jsx "AC-1: renders a PageHeader ... no emoji in headings"	frontend/src/pages/ComplianceHub.jsx (PageHeader)
AC-2	ComplianceHub.test.jsx "AC-2: no hardcoded hex colors or system-ui literals remain"	frontend/src/pages/ComplianceHub.jsx (all styles → var(--*) tokens)
AC-3	local token-styled Card retained (no shared Card exists; Out of Scope forbids new shared components); single api helper consolidated	frontend/src/pages/ComplianceHub.jsx (Card, api)
AC-4	ComplianceHub.test.jsx "AC-4: disclaimer footer wording preserved verbatim" + all 31 prior CHUB section tests still green	frontend/src/pages/ComplianceHub.jsx
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
