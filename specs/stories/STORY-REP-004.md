# STORY-REP-004: Add custom date-range picker UI for "Custom" preset

**Status:** ready
**Screen/Area:** Reports / Analytics

## Goal
When the user selects "Custom" from the date preset dropdown, a date-range picker UI appears (two date input fields) allowing start and end date selection. The picker is removed when any other preset is selected.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the "Custom" preset is selected, When the date dropdown closes, Then two date input fields (start date, end date) appear below the preset selector
- AC-2: Given both date fields are populated, When the user clicks outside the picker or presses Enter, Then the date range is applied and charts update
- AC-3: Given "Custom" was previously selected but now a different preset is selected, When the preset changes, Then the date picker UI is hidden
- AC-4: Given a date input is focused, When the user clicks the calendar icon, Then a calendar picker opens (or native date picker on mobile)
- AC-5: Given an invalid date range (end date before start date) is entered, When the user attempts to apply, Then an error message appears and the range is not applied

## Edge Cases
- User selects the same date for start and end (single day) → this is valid; apply the filter
- User clears one or both date inputs → show a "Both dates required" message
- Calendar picker is opened on mobile → use native `<input type="date">` for better UX

## Out of Scope
- Time-of-day selection (start of day / end of day will be assumed server-side)
- Keyboard-only calendar navigation (date inputs can be used instead)
- Date range templates (e.g., "This quarter")

## Non-Functional Requirements
- Date picker must be accessible (aria-labels, keyboard navigation, screen reader friendly)
- Mobile: use native date input for better touch experience
- Date validation must be consistent across client and server
- Date picker opens/closes with <200ms animation

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | e2e_custom_preset_shows_picker | Reports.jsx, components/DateRangePicker.jsx |
| AC-2 | e2e_custom_range_apply | components/DateRangePicker.jsx, Reports.jsx |
| AC-3 | test_custom_picker_hide_on_preset_change | Reports.jsx |
| AC-4 | e2e_calendar_icon_open, test_native_date_mobile | components/DateRangePicker.jsx |
| AC-5 | test_invalid_date_range_error | components/DateRangePicker.jsx, api/validation.js |

---
