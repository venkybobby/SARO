# Story Specs

One file per story. Workflow — nothing is ever pasted into chat:

1. Copy `_TEMPLATE.md` → `STORY-###.md`, fill it in, set Status: ready.
2. In Claude Code: `/story STORY-###`
3. The command enforces Definition of Ready, the TDD loop, all gates,
   independent review, and the regression/ratchet policies automatically.

A story with missing acceptance criteria will be rejected at step 0 —
underspecified stories are the root cause of review churn.


## Legacy bundle summaries (relocated by STORY-108)


### From `SARO_RiskForm_Stories.md`

## Implementation Notes
- Modify `validate()` function signature to accept an optional `field` parameter; when provided, validate only that field.
- Add `onBlur={handleFieldBlur}` to each form input; `handleFieldBlur` calls `validate(fieldName)` and updates `errors[fieldName]`.
- Ensure `onChange` still clears the error for that field to provide immediate positive feedback.
- Use existing error state structure (`errors` object in RiskForm state).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `RiskForm.test.jsx`: "AC-1: shows an inline error when a required field is left empty on blur", "AC-1/NFR: error messages are associated with their field via aria-describedby" | RiskForm.jsx, RiskForm.test.jsx |
| AC-2 | `RiskForm.test.jsx`: "AC-2: clears the error immediately when the field is corrected (onChange)" | RiskForm.jsx, RiskForm.test.jsx |
| AC-3 | `RiskForm.test.jsx`: "AC-3: submit still validates all required fields at once" | RiskForm.jsx, RiskForm.test.jsx |
| AC-4 | `RiskForm.test.jsx`: "AC-4: correcting one error leaves remaining errors and does not submit" | RiskForm.jsx, RiskForm.test.jsx |

**Edge cases covered:** rapid tab-through, clear-after-correction stays errored, pre-filled edit-mode does not error on initial render — all in `RiskForm.test.jsx`.

**Note:** "Read-only mode" edge case is N/A — RiskForm has no read-only/view mode in this codebase.

---

## Implementation Notes
- Search RiskForm.jsx for all inline hex color references: #fca5a5, #d1d5db, #ef4444, etc.
- Replace `color: "#ef4444"` with `color: "var(--color-critical)"`.
- Replace border/background colors similarly using appropriate tokens.
- If a specific tone (e.g., light gray for disabled) is needed and no token exists, flag for design review (do not invent new hardcoded colors).
- Update the `inputStyle` and `labelStyle` objects to use tokens.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `RiskForm.test.jsx`: "AC-1: contains no hardcoded hex color literals" | RiskForm.jsx, RiskForm.test.jsx |
| AC-2 | `RiskForm.test.jsx`: "AC-2: error state uses var(--color-critical) for border and error text" | RiskForm.jsx, RiskForm.test.jsx |
| AC-3 | `RiskForm.test.jsx`: "AC-3: default (non-error) input border uses var(--color-border-default)" | RiskForm.jsx, RiskForm.test.jsx |
| AC-4 | Manual contrast audit (see below) | RiskForm.jsx |

**AC-4 contrast audit (computed against `frontend/src/styles/tokens.css`):**
- `--color-critical` (#E8443A) on `--color-bg-elevated` (#1C2028): **~4.0:1** — just under the 4.5:1 AA threshold for small text (11px error text/asterisks).
- `--color-border-default` (rgba(255,255,255,0.10)) on `--color-bg-elevated`: **~1.4:1** — under the 3:1 AA threshold for borders.

Both are **existing global design tokens** used elsewhere in the app (e.g. Dashboard posture banners/badges); per this story's Out of Scope ("Modifying the design token definitions themselves" / "Creating new tokens"), the token *values* cannot be changed here. Flagging as a follow-up design-system finding rather than blocking this token-substitution story.

**Edge cases (disabled state, focus ring):** N/A — RiskForm has no `disabled` inputs or focus-ring styling currently; nothing to migrate to a token for those states (consistent with the N/A read-only-mode note in STORY-RISKFORM-001).

---

## Implementation Notes
- Track form changes in state: initialize `isDirty = false` on load.
- Set `isDirty = true` on first change to any field (onChange handler).
- Set `isDirty = false` after successful save.
- Add `beforeunload` event listener to window (for browser back/refresh).
- Add check in router navigation guards or link click handlers (for sidebar navigation).
- Use a confirmation modal component (or native `window.confirm` as fallback) to show the warning.
- Cancel button click should call the confirmation guard (not navigate directly).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `RiskForm.test.jsx`: "AC-1: dirty form + Cancel shows 'Discard unsaved changes?' confirmation" | RiskForm.jsx, RiskForm.test.jsx |
| AC-2 | `RiskForm.test.jsx`: "AC-2: registers a dirty guard so App-level (sidebar) navigation can be intercepted"; `useDirtyNavGuard.test.js` (5 unit tests covering immediate-navigate, defer+pendingNav, confirmNav, cancelNav, guard-clear). App-level interception implemented via the shared `useDirtyNavGuard` hook (`hooks/useDirtyNavGuard.js`), wired into App.jsx (`AppShell.handleNavigate`/`registerDirtyGuard`) and shown with the same `ConfirmDialog`. Browser back/refresh covered by the `beforeunload` test. | RiskForm.jsx, App.jsx, hooks/useDirtyNavGuard.js, RiskForm.test.jsx, hooks/useDirtyNavGuard.test.js |
| AC-3 | `RiskForm.test.jsx`: "AC-3: confirming 'Discard changes' navigates away without saving" | RiskForm.jsx, RiskForm.test.jsx |
| AC-4 | `RiskForm.test.jsx`: "AC-4: choosing 'Keep editing' stays on the form with edits intact" | RiskForm.jsx, RiskForm.test.jsx |
| AC-5 | `RiskForm.test.jsx`: "AC-5: after a successful save, the dirty flag resets so Cancel no longer prompts" | RiskForm.jsx, RiskForm.test.jsx |

**Edge cases:**
- Pre-filled edit mode + no changes + Cancel → no confirmation: `RiskForm.test.jsx` "edge case: pre-filled edit mode with no changes + Cancel does NOT prompt".
- Type-then-revert still counts as dirty: `RiskForm.test.jsx` "edge case: typing then reverting a value still counts as dirty".
- Modal/drawer close triggers guard: **N/A** — RiskForm is rendered as a full page via `onNavigate` (App.jsx `PAGE_COMPONENTS`), not inside a modal/drawer in this codebase. No modal/drawer host to wire up.
- Session expiry should not trigger the guard: `RiskForm.test.jsx` "session expiry / unmount: cleans up listeners and the dirty guard without throwing" — App-level token-expiry redirect unmounts RiskForm directly (no `beforeunload`/in-app guard fires for an unmount triggered by the host, only for user-initiated navigation).

**Accessibility (NFR):** `ConfirmDialog` (`components/ui/index.jsx`) traps Tab focus within the dialog while open, moves initial focus to the first focusable element on open, and restores focus to the previously-focused element on close (escape-to-cancel via a stable `onCancelRef` so re-renders of the parent don't re-run the focus trap), in addition to the existing `role="dialog"`/`aria-modal` behavior. Covered by `components/ui/ConfirmDialog.test.jsx` (initial focus + restore-on-close, and no focus-stealing on parent re-render while open).

---

## Implementation Notes
- Locate action row container in RiskForm.jsx (currently around line 199 with `marginLeft: "auto"`).
- Add `flexWrap: "wrap"` to the container style object.
- Optionally restructure with a two-row layout:
  - Row 1 (on desktop): buttons on the left, disclaimer on the right.
  - Row 1 (on mobile): buttons on the left; Row 2: disclaimer below.
- Use CSS media query or responsive flex direction if needed.
- Verify buttons and disclaimer remain aligned and readable.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `RiskForm.test.jsx`: "AC-1/AC-3/AC-4: action row uses flex-wrap so it reflows on narrow/constrained widths" — action row container now has `flexWrap: "wrap"`, allowing the disclaimer to drop to its own line on narrow viewports without pushing the Save/Cancel buttons off-screen. | RiskForm.jsx, RiskForm.test.jsx |
| AC-2 | `RiskForm.test.jsx`: "AC-2: Save and Cancel buttons sit in the same row container as the disclaimer" — on wide viewports all three elements remain on one row (`marginLeft: "auto"` keeps the disclaimer right-aligned with adequate `gap`). | RiskForm.jsx, RiskForm.test.jsx |
| AC-3 | Covered by the same `flexWrap: "wrap"` + `gap` CSS as AC-1/AC-4 (jsdom does not compute responsive layout/resize, so behavior is verified via the static style assertions above; full viewport-resize visual verification is a manual/Playwright follow-up, consistent with this story's "Out of Scope"/manual-test notes). | RiskForm.jsx |
| AC-4 | Same `flexWrap: "wrap"` CSS handles arbitrary container widths generically (modal/drawer constrained width); see AC-3 note re: jsdom layout limitations. | RiskForm.jsx |

**Edge cases:**
- Disabled Save button doesn't break layout: `RiskForm.test.jsx` "edge case: a disabled Save button does not break the action row layout".
- Long/wrapping disclaimer text: `RiskForm.test.jsx` "disclaimer text is allowed to wrap onto multiple lines (no forced single line)" — `whiteSpace` is not set to `nowrap`, and `minWidth: 200` on the disclaimer `<span>` ensures it moves to its own line as a unit (rather than being squeezed) once the row can't fit it alongside the buttons.
- Extremely narrow (<320px) / RTL: not separately tested — `flexWrap: "wrap"` and `gap`-based spacing degrade gracefully and are direction-agnostic, but pixel-level verification at 320px and RTL layouts is left to manual/Playwright visual QA (out of scope for this unit-test pass, per story's E2E note).

---

## Summary

| Story | Issue | Priority | Est. Effort |
|-------|-------|----------|------------|
| STORY-RISKFORM-001 | #1: Validation only runs on submit | Major | M |
| STORY-RISKFORM-002 | #2: Hardcoded colors instead of tokens | Major | M |
| STORY-RISKFORM-003 | #4: No unsaved-changes warning | Minor | M |
| STORY-RISKFORM-004 | #5: Action row layout cramped | Minor | S |

**Issue #3** (required/optional visual distinction) is resolved by STORY-RISKFORM-002 (token consistency ensures asterisk color matches).  
**Issue #6** (date picker) is a Pass; no story created.


### From `SARO_Stories_Reports_Settings_Nav_Mobile.md`

## Settings / Configuration Screen

---

## Navigation & Global Components Screen

---

## Responsive / Mobile Experience Screen

---

## Summary

**Total Stories: 26**

| Screen | Stories | IDs |
|--------|---------|-----|
| Reports / Analytics | 6 | REP-001 through REP-005 |
| Settings / Configuration | 5 | SET-001 through SET-005 |
| Navigation & Global | 6 | NAV-001 through NAV-006 |
| Responsive / Mobile | 5 | MOB-001 through MOB-005 |

**Dependency Map:**
- **REP-001** (Recharts integration) → blocks REP-002, REP-003
- **REP-003** (Date filtering) → depends on REP-001
- **SET-002** (Wire settings API) → foundational for other Settings stories
- **SET-005** (Refactor settings nav) → cleanup task; can run parallel to others
- **NAV-001** (Responsive sidebar) → blocks NAV-002, MOB-001
- **NAV-004** (Focus trap) → depends on NAV-002, NAV-003; enables NAV-005
- **NAV-005** (Shared Modal) → cleanup task after NAV-004
- **MOB-001, MOB-002, MOB-003, MOB-004** → all depend on NAV-001 (responsive foundation)

**Ready for Sprint Planning:**
All stories are in **draft** or **ready** status. Ready stories can be pulled into sprints immediately.
