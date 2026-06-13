# STORY-MOB-005: Add "Print" button to Reports and clean up dead .mobile-tab-bar reference

**Status:** ready
**Screen/Area:** Responsive / Mobile Experience

## Goal
Two related tasks: (1) Add a visible "Print Report" button to the Reports toolbar (from REP-005, but highlighted here for mobile context), and (2) Remove or implement the dead .mobile-tab-bar CSS class referenced in global.css:45 that doesn't exist anywhere in the codebase.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the Reports page toolbar is displayed, When the user looks for print functionality, Then a "Print Report" button is visible alongside Export/Share controls
- AC-2: Given the user clicks "Print Report" on mobile, When the print dialog opens, Then the sidebar and toolbar are hidden (per existing @media print rules) and only the charts/content are visible
- AC-3: Given the global.css file is audited, When .mobile-tab-bar reference (line 45) is found, Then either: (a) implement a real .mobile-tab-bar class for the Settings tab bar (MOB-004), or (b) remove the dead reference and the associated print rule
- AC-4: Given the mobile tab bar is implemented (if option a), When @media print is applied, Then the tab bar is correctly hidden or shown based on the final design decision

## Edge Cases
- User prints from mobile Safari → print preview should show correctly formatted content
- Print button is tapped while charts are loading → disable button or show "Waiting for charts..."

## Out of Scope
- Mobile-specific print styling beyond standard responsive behavior

## Non-Functional Requirements
- Print button is at least 44x44px on mobile
- Print layout must be black-and-white friendly
- No console errors related to .mobile-tab-bar removal

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_mobile_print_button | Reports.jsx |
| AC-2 | e2e_mobile_print_dialog | Reports.jsx, global.css |
| AC-3 | test_mobile_tab_bar_cleanup | global.css |
| AC-4 | visual_mobile_print_tab_bar | global.css, Settings.jsx |

---
