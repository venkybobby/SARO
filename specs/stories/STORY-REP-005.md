# STORY-REP-005: Surface print report functionality with "Print Report" button

**Status:** ready
**Screen/Area:** Reports / Analytics

## Goal
Add a visible "Print Report" button to the Reports page toolbar that triggers window.print(). Print styles already exist in global.css; this story surfaces them to users and tests the full print flow end-to-end.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Reports page is displayed, When the user looks at the toolbar, Then a "Print Report" button is visible next to Export and Share controls
- AC-2: Given the user clicks "Print Report", When the browser print dialog opens, Then the page is formatted correctly (no sidebar, toolbar hidden, charts visible)
- AC-3: Given the user cancels the print dialog, When the dialog closes, Then the Reports page is unchanged and fully interactive
- AC-4: Given a report is printed, When the printout is rendered, Then all five charts are visible (no page breaks within charts)
- AC-5: Given the user prints the report, When the printout is saved as PDF, Then the file name is "SARO-Report-YYYY-MM-DD.pdf"

## Edge Cases
- User's printer is offline → browser print dialog handles this; SARO does nothing
- Charts are still loading when print is triggered → show a "Waiting for charts to load..." state and disable the button
- Print is triggered on mobile → preview should allow landscape orientation

## Out of Scope
- Custom print templates or report layouts
- Scheduled/automated printing
- Email printing (use REP-002 for email distribution)

## Non-Functional Requirements
- Print button is accessible (keyboard focusable, aria-label)
- Print styles must hide everything except main content (sidebar, navbar, footer, toolbar)
- Charts must fit on standard letter/A4 without excessive page breaks
- Print output must be black-and-white friendly (colors remain but don't rely on them)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_print_button_visible | Reports.jsx |
| AC-2 | e2e_print_dialog_open, visual_print_preview | Reports.jsx |
| AC-3 | e2e_print_cancel_no_change | Reports.jsx |
| AC-4 | visual_print_charts_visible, test_print_page_breaks | global.css |
| AC-5 | test_print_filename_format | Reports.jsx, utils/formatters.js |

---
