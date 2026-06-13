# STORY-AIINSIGHTS-005: Tie AI Loading State to Real Data Fetch

**Status:** done — implemented on `story/SARO_AIInsights_Stories` (2026-06-11)
**Screen/Area:** AI Insights / Loading State / UX

## Goal
The "AI is thinking" loading indicator reflects actual backend response time, starting when the fetch begins and ending when data arrives, eliminating artificial 2.2s delays and preventing dark-pattern UX that misleads users into thinking the AI is "reasoning" when data was already cached.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the AIInsights component is mounted, When the data fetch begins, Then AIThinkingState is set to true immediately (not after a delay)
- AC-2: Given a fetch request is in-flight, When the backend responds successfully, Then AIThinkingState is set to false immediately upon data arrival (not after a fixed 2.2s timeout)
- AC-3: Given a slow network response (e.g., 5s), When the data arrives, Then the loading spinner is visible for the entire 5s duration, accurately reflecting the wait time
- AC-4: Given a fast response (e.g., 300ms), When data arrives, Then the spinner is hidden after 300ms—not held for 2.2s
- AC-5: Given an error occurs during fetch, When the error is caught, Then the loading state is cleared immediately and an error message is shown

## Edge Cases
- Multiple rapid navigations (user clicks insights tab, then another tab, then back) — cancel in-flight requests and reset loading state cleanly
- Network timeout (no response after 10s) — show timeout error, not indefinite loading spinner
- Data fetch succeeds but is empty (valid but no insights) — hide loading spinner, show empty state, not error
- Very fast cached responses (<50ms) — may show brief spinner or skip it entirely (product decision)

## Out of Scope
- Artificial delays elsewhere in the UI (that is a separate refactor)
- Skeleton loader design (assume simple spinner or placeholder; styling is STORY-006 or design spec)
- Streaming/progressive data loading (fetch all-at-once for MVP)

## Non-Functional Requirements
- Loading state must be bound to the actual Promise/fetch lifecycle, not setTimeout
- Spinner should be clear that it represents "loading data", not "AI reasoning" (label: "Fetching insights...")
- Network tab in dev tools should show 1:1 correlation between fetch duration and spinner visibility
- Logging: log fetch start, response time, and loading state changes

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | "AC-1: loading shows immediately when the fetch starts" | frontend/src/pages/AIInsights.jsx |
| AC-2 | "AC-2/AC-4: loading clears the moment data arrives — no fixed delay" | frontend/src/pages/AIInsights.jsx |
| AC-3 | "AC-3: loading persists exactly while the request is in flight" (deferred-promise test) | frontend/src/pages/AIInsights.jsx |
| AC-4 | covered by the AC-2/AC-4 test (promise resolution clears loading with no timer) | frontend/src/pages/AIInsights.jsx |
| AC-5 | "AC-5: loading clears on fetch error" | frontend/src/pages/AIInsights.jsx |

Edge/NFR: 10s timeout ("aborts after the timeout and flags timedOut", insightsService.test.js); in-flight abort on unmount/refetch (AbortController in load()); honest label + no artificial delay pinned by source assertion ("NFR: no artificial setTimeout delay remains and the label is honest"); empty-but-valid response shows empty state, not error.

---
