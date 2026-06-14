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
