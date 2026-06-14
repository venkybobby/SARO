# STORY-AIINSIGHTS-006: Optimize Filter Tab Discoverability

**Status:** done — implemented on `story/SARO_AIInsights_Stories` (2026-06-11)
**Screen/Area:** AI Insights / Filter Tabs

## Goal
Filter tabs with zero insights (0 count) are visually de-emphasized or hidden so users naturally focus on the "Active" tab first, improving UX discoverability and reducing cognitive load when browsing suggestions.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given AI Insights displays four filter tabs (Active, Accepted, Snoozed, Dismissed), When a tab has zero insights, Then the tab is styled with reduced opacity (e.g., 50%) or grayed-out text color
- AC-2: Given the "Active" tab contains insights and others do not, When the user views the screen, Then "Active" visually stands out (bold, higher contrast, or primary color)
- AC-3: Given a user hovers over a (0) tab, When they hover, Then a tooltip appears: "No items in this category" or similar, making the empty state explicit
- AC-4: Given insights are accepted/snoozed/dismissed, When those tabs gain insights, Then the styling updates in real-time to de-emphasize "Active" and emphasize the now-populated tab

## Edge Cases
- All tabs are empty (no insights at all) — show all tabs normally, display "No insights yet" message in content area
- Very long tab labels with large counts (e.g., "Active (999)") — ensure layout does not wrap or misalign
- User has no insights permission for a tab (e.g., auditor cannot see "Dismissed") — hide that tab entirely, do not show (0)
- Mobile view — ensure reduced opacity tabs are still tappable and clear

## Out of Scope
- Hiding empty tabs completely (assume they remain visible for discoverability)
- Reordering tabs based on population (assume current order is intentional)
- Analytics on which tab users click first (defer to product analytics)

## Non-Functional Requirements
- Styling: empty tabs should use CSS class or conditional style, not hardcoded gray color (for consistency with theme)
- Accessibility: reduced opacity tabs must remain keyboard-accessible and screen-reader friendly; do not use opacity alone as the indicator
- Mobile: ensure touch target size (min 44px) is maintained even for de-emphasized tabs
- Performance: tab switching should not trigger unnecessary re-renders of insight lists

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | "AC-1: zero-count tabs are de-emphasized" (opacity 0.55 + muted color + aria-label) | frontend/src/pages/AIInsights.jsx |
| AC-2 | "AC-2: the populated active tab stands out" (aria-current, full opacity, semibold) | frontend/src/pages/AIInsights.jsx |
| AC-3 | "AC-3: empty tabs carry the tooltip" (title="No items in this category") | frontend/src/pages/AIInsights.jsx |
| AC-4 | "AC-4: styling updates when an insight changes state" | frontend/src/pages/AIInsights.jsx |

Edge/NFR: all-tabs-empty renders normally ("edge: when everything is empty, tabs render normally"); 44px touch targets kept when de-emphasized ("NFR: touch targets keep a 44px minimum height"); de-emphasis is never opacity alone (aria-label carries the state for screen readers).
