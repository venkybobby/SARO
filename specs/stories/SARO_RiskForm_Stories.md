# STORY-RISKFORM-001: Real-Time Field Validation (onBlur)

**Status:** ready  
**Screen/Area:** Risk Creation / Edit Form

## Goal
Users see validation errors on individual fields as they move through the form (onBlur), not just when attempting to submit. This reduces friction and helps correct mistakes before hitting Save.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given a user is editing the Risk Form, When they leave a required field (Title, Owner, Due Date) empty and move to the next field (onBlur), Then an inline error message appears below that field.
- AC-2: Given a user has triggered an error on a field, When they edit that field to correct the value, Then the error message clears immediately (onChange).
- AC-3: Given a user attempts to Submit with validation errors remaining, When they click Save, Then the existing submit validation runs and highlights all invalid fields at once.
- AC-4: Given a user has multiple validation errors, When they correct the first error and it clears, Then the form does not auto-submit; they remain on the form to fix remaining errors.

## Edge Cases
- User tabs rapidly through fields without pausing (onBlur fires in sequence; errors appear/clear as expected).
- User enters invalid data, triggers error, then clears the field entirely (should remain in error state until valid data is entered).
- User opens form in edit mode with pre-filled data and invalid state (initial render should not trigger errors; only subsequent onBlur events do).
- User opens form with read-only mode (if applicable); onBlur handlers should not fire.

## Out of Scope
- Custom error messages per field (use standard "Field is required" or "[Field name] is invalid").
- Async validation (e.g., checking if an Owner exists in the database); defer to future story.
- Server-side validation error handling (handled separately by API integration).

## Non-Functional Requirements
- Validation must complete in <100ms per field.
- No performance degradation on forms with 10+ fields.
- Error colors must use `var(--color-critical)` (not hardcoded #ef4444).
- Accessibility: error messages associated with field via `aria-describedby`.

## Implementation Notes
- Modify `validate()` function signature to accept an optional `field` parameter; when provided, validate only that field.
- Add `onBlur={handleFieldBlur}` to each form input; `handleFieldBlur` calls `validate(fieldName)` and updates `errors[fieldName]`.
- Ensure `onChange` still clears the error for that field to provide immediate positive feedback.
- Use existing error state structure (`errors` object in RiskForm state).

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | E2E: required field onBlur → error appears | RiskForm.jsx, E2E test suite |
| AC-2 | E2E: correct field → error clears | RiskForm.jsx, E2E test suite |
| AC-3 | E2E: submit with remaining errors | RiskForm.jsx, E2E test suite |
| AC-4 | E2E: fix one error, form does not submit | RiskForm.jsx, E2E test suite |

---

# STORY-RISKFORM-002: Replace Hardcoded Colors with Design Tokens

**Status:** ready  
**Screen/Area:** Risk Creation / Edit Form

## Goal
Eliminate hardcoded hex colors (#fca5a5, #d1d5db, #ef4444) in RiskForm.jsx and use project design tokens (var(--color-critical), var(--color-border-default), etc.) for consistency and proper contrast support across light/dark modes.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Risk Form is rendered on any background theme, When the form displays with any color (border, error text, success state), Then all colors use CSS custom properties (var(--color-*)) from the design token system.
- AC-2: Given the form renders with error states, When an error field is shown, Then the error text and border use `var(--color-critical)` (not #ef4444).
- AC-3: Given the form renders with default (non-error) state, When an input border is drawn, Then it uses `var(--color-border-default)` (not #d1d5db).
- AC-4: Given the form is viewed on light or dark mode, When the CSS is applied, Then contrast ratios for all text/border combinations meet WCAG AA minimum (4.5:1 for text, 3:1 for borders).

## Edge Cases
- Form inputs with `disabled` state (ensure border/background tokens for disabled state are applied).
- Form inputs with `focus` state (ensure focus ring uses `var(--color-focus-ring)` or equivalent).
- Optional fields with no error (ensure default border token is not too light).
- Required field indicators (* asterisk color must use `var(--color-critical)`, not hardcoded #ef4444).

## Out of Scope
- Modifying the design token definitions themselves (assume tokens are already defined in global CSS).
- Creating new tokens (use only existing tokens).
- Refactoring other screens' hardcoded colors (this story is Risk Form only).

## Non-Functional Requirements
- All inline `style={}` objects replaced with CSS classes referencing tokens, or inline styles updated to use `var()` notation.
- No performance impact; CSS variable lookup is negligible.
- Accessibility: verify no contrast regressions with axe-core or similar audit tool.

## Implementation Notes
- Search RiskForm.jsx for all inline hex color references: #fca5a5, #d1d5db, #ef4444, etc.
- Replace `color: "#ef4444"` with `color: "var(--color-critical)"`.
- Replace border/background colors similarly using appropriate tokens.
- If a specific tone (e.g., light gray for disabled) is needed and no token exists, flag for design review (do not invent new hardcoded colors).
- Update the `inputStyle` and `labelStyle` objects to use tokens.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | Code review: no #[hex] in RiskForm.jsx | RiskForm.jsx |
| AC-2 | Unit/E2E: error state uses --color-critical | RiskForm.jsx, visual regression test |
| AC-3 | Unit/E2E: default border uses --color-border-default | RiskForm.jsx, visual regression test |
| AC-4 | Accessibility audit: WCAG AA contrast verified | axe-core, manual spot-check |

---

# STORY-RISKFORM-003: Unsaved Changes Guard (Dirty Form Detection)

**Status:** ready  
**Screen/Area:** Risk Creation / Edit Form

## Goal
Warn users before navigating away from an unsaved Risk Form (via Cancel button, sidebar navigation, or browser back button). This prevents accidental data loss.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given a user has made changes to the Risk Form (form is "dirty"), When they click the Cancel button, Then a modal confirmation appears: "Discard unsaved changes?"
- AC-2: Given a user has made changes to the Risk Form and they attempt to navigate to another screen via the sidebar, When the navigation event fires, Then a beforeunload/navigation guard triggers and shows a confirmation dialog.
- AC-3: Given a user has made changes and they confirm "Discard changes", When the confirmation is accepted, Then the form closes/navigates away without saving.
- AC-4: Given a user has made changes and they select "Keep editing" in the confirmation, When the confirmation is dismissed, Then they remain on the Risk Form with all edits intact.
- AC-5: Given a user saves the form successfully, When the save completes, Then the dirty flag is reset so navigating away does not trigger the confirmation.

## Edge Cases
- User opens form in edit mode with pre-filled data; making no changes and clicking Cancel should NOT trigger the confirmation.
- User makes a change, then reverts it (e.g., types "test" then deletes it); form should detect the change as dirty even if the final value matches the original.
- User opens form in a modal/drawer; closing the modal should trigger the guard.
- User's session expires; the guard should allow them to leave without triggering a warning about unsaved changes.

## Out of Scope
- Auto-save functionality (separate feature; this story is guard/warning only).
- Persist unsaved form state to localStorage (future enhancement).
- Server-side conflict detection (e.g., another user edited the same risk).

## Non-Functional Requirements
- Guard must fire within <500ms of navigation attempt.
- Confirmation modal must be non-blocking and non-intrusive (standard browser dialog or styled modal, not a system alert).
- Dirty flag is tracked in component state (e.g., `formState.isDirty`).
- Accessibility: modal is keyboard navigable; focus is trapped and returns to form on dismiss.

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
| AC-1 | E2E: edit form, click Cancel → confirmation modal | RiskForm.jsx, E2E test suite |
| AC-2 | E2E: edit form, navigate sidebar → confirmation modal | Router/Navigation, E2E test suite |
| AC-3 | E2E: confirm discard → navigate away | RiskForm.jsx, E2E test suite |
| AC-4 | E2E: dismiss confirmation → stay on form | RiskForm.jsx, E2E test suite |
| AC-5 | E2E: save form → no confirmation on next nav | RiskForm.jsx, E2E test suite |

---

# STORY-RISKFORM-004: Fix Action Row Layout (Disclaimer Text Wrapping)

**Status:** ready  
**Screen/Area:** Risk Creation / Edit Form

## Goal
Resolve the cramped action row layout where the "Human review required..." disclaimer text wraps awkwardly on narrow viewports. Improve readability and button accessibility by restructuring the row with proper flex wrapping.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Risk Form is displayed on a narrow viewport (mobile, <768px), When the Save/Cancel buttons and disclaimer text are rendered, Then the disclaimer wraps to a new line cleanly without pushing buttons off-screen.
- AC-2: Given the action row is displayed on desktop, When both buttons and disclaimer are present, Then they remain on the same row with adequate spacing and the disclaimer does not crowd the buttons.
- AC-3: Given the action row is resized (viewport width changes), When the flex layout reflows, Then the transition is smooth and buttons are always accessible (tappable/clickable).
- AC-4: Given the form is in a modal or drawer, When the action row width is constrained, Then all elements (Save, Cancel, disclaimer) remain visible and properly spaced.

## Edge Cases
- Disclaimer text is very long (future i18n with longer translations); ensure it wraps without truncation.
- One button is disabled (e.g., Save is disabled pending validation); spacing remains consistent.
- Screen is extremely narrow (< 320px); disclaimer should stack above buttons if needed (graceful degradation).
- RTL languages (if applicable); flex direction and text alignment must adapt.

## Out of Scope
- Changing the disclaimer text itself (content review is separate).
- Moving the disclaimer to a tooltip or popover (layout-only fix; future UX enhancement).
- Modifying button styles or labels.

## Non-Functional Requirements
- Action row container must have `flexWrap: "wrap"` or equivalent CSS (`flex-wrap: wrap`).
- Spacing (gap/margin) must remain consistent after wrap (use CSS `gap` property).
- No horizontal scroll on any viewport size.
- Mobile-first: test at 320px, 375px, 768px, 1024px, 1920px.

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
| AC-1 | E2E/Visual: narrow viewport action row wraps | RiskForm.jsx, responsive test suite |
| AC-2 | E2E/Visual: desktop action row stays on one line | RiskForm.jsx, responsive test suite |
| AC-3 | E2E/Visual: viewport resize reflow test | RiskForm.jsx, responsive test suite |
| AC-4 | E2E/Visual: modal/drawer constrained width | RiskForm.jsx, modal test suite |

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
