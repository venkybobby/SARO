# STORY-REP-001: Integrate Recharts charting library and render five analytics charts

**Status:** ready
**Screen/Area:** Reports / Analytics

## Goal
Replace all five ChartPlaceholder stubs with functional Recharts components (Overview, Compliance Trends, Risk Distribution, Forecast, and Audit Trail). Users can see real data visualized with dark-theme support and responsive sizing.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given Recharts is installed and configured, When Reports.jsx renders, Then each of the five charts (Overview, Compliance Trends, Risk Distribution, Forecast, Audit Trail) displays real data (not EmptyState placeholder text)
- AC-2: Given a chart is displayed, When viewport is resized, Then chart scales responsively without breaking layout
- AC-3: Given a date range filter is applied, When data updates, Then chart data reflects the filtered date range
- AC-4: Given the user is in dark mode, When a chart renders, Then colors are legible and match the dark theme palette
- AC-5: Given five charts are rendered, When page load completes, Then bundle size increase from Recharts is <85KB gzipped

## Edge Cases
- Chart data is empty or null for a given date range → display a "No data for this period" message instead of a blank area
- Chart renders with an extremely large dataset (>10k rows) → consider sampling or truncation to avoid performance degradation
- User rapidly changes date presets → debounce chart re-renders to avoid flickering

## Out of Scope
- Custom chart styling beyond dark-theme defaults
- Chart drill-down or interactive data exploration
- Exporting chart data (covered in REP-002)

## Non-Functional Requirements
- Chart re-render latency: <300ms on 10k-row datasets
- No console errors or warnings
- Accessibility: all charts have descriptive aria-labels and keyboard-navigable legends
- Mobile: charts remain readable at 320px viewport width

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | test_reports_charting_integration, e2e_reports_charts_render | Reports.jsx, components/charts/ |
| AC-2 | test_chart_responsive_resize | global.css, Reports.jsx |
| AC-3 | test_chart_data_filter_sync | Reports.jsx, api/reportService.js |
| AC-4 | visual_dark_theme_charts | components/charts/*, global.css |
| AC-5 | bundle_size_recharts_gzip | package.json, .build/report.txt |

---
