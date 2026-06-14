# STORY-NAV-004: Ensure focus is trapped in ConfirmDialog and OnboardingWizard modals

**Status:** ready
**Screen/Area:** Navigation & Global Components

## Goal
Implement focus trapping in both ConfirmDialog and OnboardingWizard modals so that Tab and Shift+Tab stay within the modal, and focus is moved to the first focusable element on open. This prevents keyboard users from accidentally tabbing to elements behind the backdrop.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given a modal (ConfirmDialog or OnboardingWizard) is open, When the user presses Tab on the last focusable element, Then focus moves to the first focusable element in the modal (wraps around)
- AC-2: Given a modal is open, When the user presses Shift+Tab on the first focusable element, Then focus moves to the last focusable element (wraps backward)
- AC-3: Given a modal is opening, When it becomes visible, Then focus automatically moves to the first focusable element (e.g., first input or primary button)
- AC-4: Given a modal is closed, When it disappears, Then focus is restored to the element that opened the modal (e.g., the button that triggered ConfirmDialog)
- AC-5: Given a modal is open and the user presses Escape, When the modal closes, Then focus is restored as per AC-4

## Edge Cases
- Modal has no focusable elements → focus is moved to the modal container itself (role="dialog" element)
- Modal is nested (modal within modal) → inner modal traps focus; outer modal regains focus when inner closes
- User selects text in the modal with mouse → Tab should still trap focus correctly

## Out of Scope
- Virtual focus management for screen readers (that's a separate a11y story)
- Custom focus management per modal

## Non-Functional Requirements
- Focus trap must work with dynamic content (e.g., buttons added/removed after open)
- Must not conflict with form-submission focus management (Shift+Enter, etc.)
- All tests must pass (no regression to existing modal behavior)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | a11y_focus_trap_tab_wrap | ui/index.jsx |
| AC-2 | a11y_focus_trap_shift_tab_wrap | ui/index.jsx |
| AC-3 | a11y_focus_move_on_open | ui/index.jsx, App.jsx |
| AC-4 | a11y_focus_restore_on_close | ui/index.jsx, App.jsx |
| AC-5 | a11y_focus_restore_escape_close | ui/index.jsx |

---
