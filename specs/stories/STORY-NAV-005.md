# STORY-NAV-005: Extract shared Modal wrapper used by both ConfirmDialog and OnboardingWizard

**Status:** ready
**Screen/Area:** Navigation & Global Components

## Goal
After implementing focus trapping (NAV-004), refactor ConfirmDialog and OnboardingWizard to share a common Modal wrapper component. This reduces code duplication, ensures consistent behavior (focus trap, Escape key, backdrop click), and makes future modal patterns easier to add.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given a new Modal wrapper component is created, When ConfirmDialog and OnboardingWizard both import and use it, Then their focus trap, Escape, and backdrop behaviors are identical
- AC-2: Given the Modal wrapper is used, When a modal is opened, Then it renders a backdrop with role="dialog" and aria-modal="true"
- AC-3: Given the Modal wrapper accepts children, When ConfirmDialog renders, Then the ConfirmDialog content is rendered inside the Modal as children
- AC-4: Given both ConfirmDialog and OnboardingWizard use Modal, When tests are run, Then all existing tests pass (no regression)
- AC-5: Given the Modal wrapper is documented, When a developer wants to add a new modal, Then they can import Modal and use it without duplicating focus/Escape/backdrop logic

## Edge Cases
- Modal is created but never opened → no errors or side effects
- Multiple modals are mounted at once (e.g., ConfirmDialog + OnboardingWizard) → focus trap applies to the topmost modal only

## Out of Scope
- Animation framework (that's orthogonal to Modal creation)
- Custom modal layouts (Modal handles structural concerns only)

## Non-Functional Requirements
- Modal wrapper must be <100 lines of code (focused responsibility)
- All props passed to Modal must be documented (JSDoc)
- TypeScript types must be clear

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | test_confirmdialog_uses_modal | ui/index.jsx, components/Modal.jsx |
| AC-2 | visual_modal_backdrop_aria | components/Modal.jsx |
| AC-3 | test_modal_children_render | components/Modal.jsx |
| AC-4 | test_no_regression_all_modal_tests | ui/index.jsx, App.jsx |
| AC-5 | doc_modal_component_readme | components/Modal.jsx |

---
