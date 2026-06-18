STORY-TRACE-009: Refactor TRACE View onto the shared design system
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P2 · Depends on: STORY-TRACE-001

Goal
`TraceView.jsx` uses hardcoded hex colors, `fontFamily: "system-ui"`, inline `<h1>` header, and local badge/chip helpers, diverging from the design-token system and shared components (`PageHeader`, `Card`, `Badge`, `Skeleton`) used elsewhere. Refactor for visual and structural consistency without changing behavior.

Framework mapping (per ADR-004 scope locks)
- No new compliance claims; presentation refactor only — wording stays scope-lock compliant (esp. the integrity element from STORY-TRACE-004).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given `TraceView.jsx`, When refactored, Then it renders a shared `PageHeader` (title "TRACE View", auditor-oriented subtitle) consistent with the Dashboard pattern.
AC-2: Given color/spacing values, When refactored, Then they use design tokens (`var(--color-*)`, `var(--space-*)`, `var(--radius-*)`) — no hardcoded hex or `system-ui` literals remain.
AC-3: Given the local `StatusBadge`/`RiskChip` styling, When refactored, Then it uses shared badge components/tokens while preserving the pass/warn/fail/pending semantics and the ≥70/≥40 risk thresholds.
AC-4: Given the refactor, When the page renders, Then all data and behavior are unchanged (pure presentation), verified by existing tests.

Edge Cases
- The integrity banner's verified/broken/unavailable states keep their semantic colors after tokenization.
- The pipeline strip remains horizontally scrollable on narrow viewports.

Out of Scope
- Behavioral fixes (STORY-TRACE-001..008).
- New shared components — reuse existing ones.

Non-Functional Requirements
- Diff is style/structure only; no net change to rendered data.
- Passes `pre-edit-standards-check.sh`.

Test Requirements
- Frontend unit (`TraceView.test.jsx`): renders `PageHeader`; no `#`-hex/`system-ui` literals in style props; badge semantics and thresholds unchanged; prior section tests pass.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
