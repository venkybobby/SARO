# STORY-NAV-003: Add Escape key handler to persona switcher dropdown for consistency

**Status:** ready
**Screen/Area:** Navigation & Global Components

## Goal
The persona switcher dropdown currently closes on outside click but not on Escape. Add Escape key handling to match the ConfirmDialog pattern and improve keyboard usability.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the persona switcher dropdown is open, When the user presses Escape, Then the dropdown closes
- AC-2: Given the dropdown is open and Escape is pressed, When it closes, Then focus remains on the persona switcher button (not lost to the body)
- AC-3: Given nested modals exist (e.g., dropdown + ConfirmDialog), When Escape is pressed, Then only the outermost modal closes (standard modal stacking)
- AC-4: Given the user presses Escape while the dropdown is closed, When the keystroke occurs, Then nothing happens (no error, no side effect)

## Edge Cases
- User is typing in an input field and presses Escape → the input's default Escape behavior should take precedence (or coexist)
- Multiple persona switchers on the page (unlikely but possible) → each should independently handle Escape

## Out of Scope
- Changing focus management beyond standard modal pattern
- Custom Escape behavior per persona

## Non-Functional Requirements
- Escape handler must not interfere with other Escape listeners (e.g., in modals)
- No console errors
- Code must match ConfirmDialog's Escape implementation for consistency

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | e2e_persona_dropdown_escape_close | Sidebar.jsx |
| AC-2 | test_persona_dropdown_focus_restore | Sidebar.jsx |
| AC-3 | e2e_nested_modal_escape_stacking | Sidebar.jsx, ui/index.jsx |
| AC-4 | test_escape_no_op_when_closed | Sidebar.jsx |

---
