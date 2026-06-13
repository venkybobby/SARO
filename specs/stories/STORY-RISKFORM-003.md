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
