# STORY-MOB-003: Implement responsive table layout for Reports dashboard below 768px

**Status:** ready
**Screen/Area:** Responsive / Mobile Experience

## Goal
Similar to MOB-002 but for the Reports / Analytics screen. If the Reports page contains any data tables (e.g., Audit Trail or Forecast details), convert them to card-based layout on mobile. Charts are handled separately (they should remain responsive via Recharts).

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the viewport is <768px, When a table is rendered on the Reports page, Then it displays as stacked cards (not horizontal table)
- AC-2: Given charts are displayed, When the viewport is <768px, Then charts remain in chart format (not converted to cards) and are responsive via Recharts
- AC-3: Given a card is displayed, When all columns are inspected, Then no horizontal scrolling is required
- AC-4: Given the viewport is resized to ≥768px, When the resize occurs, Then any tables return to horizontal table view and charts remain unchanged

## Edge Cases
- Reports page has no tables (only charts) → no card layout needed; skip implementation or mark as "no-op"
- Chart is extremely wide → ensure it doesn't overflow the viewport (Recharts should handle this, but verify)

## Out of Scope
- Custom chart resizing beyond Recharts defaults

## Non-Functional Requirements
- Card layout matches the Risk Register card design (MOB-002) for consistency
- Charts remain responsive without additional mobile styling

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | visual_mobile_reports_cards | Reports.jsx, global.css |
| AC-2 | visual_mobile_charts_responsive | Reports.jsx, components/charts/* |
| AC-3 | e2e_card_no_scroll | Reports.jsx |
| AC-4 | e2e_responsive_reports_return | Reports.jsx, global.css |

---
