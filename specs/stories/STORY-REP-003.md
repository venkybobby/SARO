# STORY-REP-003: Wire date range presets and drive chart data filtering

**Status:** ready
**Screen/Area:** Reports / Analytics

## Goal
Connect the datePreset state to the data-fetching logic so that selecting "Last 7 Days", "Last 30 Days", "Last 90 Days", or "Custom" actually filters the data. Charts automatically update when the preset changes.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the user selects "Last 7 Days", When the data refetches, Then all charts display only data from the past 7 days
- AC-2: Given the user selects "Last 30 Days", When the data refetches, Then all charts display only data from the past 30 days
- AC-3: Given the user selects "Last 90 Days", When the data refetches, Then all charts display only data from the past 90 days
- AC-4: Given the user selects "Custom", When a date-range picker appears, Then they can select a custom start and end date, and charts update to show that range
- AC-5: Given a preset is selected, When the data refetches, Then a loading state is shown on charts and a toast indicates "Fetching data..."

## Edge Cases
- User selects "Custom" but closes the date picker without selecting dates → maintain the previous preset
- Selected custom date range has no data → show "No data for this range" message and keep the previous chart state
- User selects a future date range → show an error: "End date cannot be in the future"

## Out of Scope
- Relative time references (e.g., "fiscal quarter") beyond the standard presets
- Saved/bookmarked date ranges
- Timezone awareness (use server-reported timezone for all calculations)

## Non-Functional Requirements
- Preset change → chart update latency: <1.5s for typical datasets
- Date picker must support keyboard navigation and screen readers
- All date formats must be locale-aware and respect user's timezone

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | test_preset_last7_data_filter | Reports.jsx, api/reportService.js |
| AC-2 | test_preset_last30_data_filter | Reports.jsx, api/reportService.js |
| AC-3 | test_preset_last90_data_filter | Reports.jsx, api/reportService.js |
| AC-4 | e2e_custom_date_picker, test_custom_range_filter | Reports.jsx, components/DateRangePicker.jsx |
| AC-5 | e2e_preset_loading_state, test_loading_toast | Reports.jsx, ui/index.jsx |

---
