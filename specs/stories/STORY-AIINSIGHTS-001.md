# STORY-AIINSIGHTS-001: Wire AI Insights to Backend Data Service

**Status:** done — implemented on `story/SARO_AIInsights_Stories` (2026-06-11)
**Screen/Area:** AI Insights / Data Wiring

## Goal
AI Insights screen fetches real compliance-scoring insights from the backend API instead of hardcoded mock data, enabling production-ready guidance delivery to compliance users.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given the AIInsights component is mounted, When the component initializes, Then a fetch call is made to `/api/insights` with the current tenant/risk context
- AC-2: Given a successful API response with insight objects, When data arrives, Then each insight is rendered in InsightCard with real {title, description, confidenceScore, framework, remediation} fields
- AC-3: Given an API error or timeout, When the request fails, Then an error state is displayed with a retry button and the mock data is NOT shown
- AC-4: Given insights are loaded, When the user navigates away and back, Then fresh data is fetched (no stale cache without explicit caching strategy)

## Edge Cases
- No insights returned (empty array) — show empty state, not mock data
- Very high confidence scores (>95%) — ensure "human validation required" framing still appears (see STORY-004)
- Slow network (>5s) — do not fall back to mock; show skeleton loader or timeout message

## Out of Scope
- Pagination or infinite scroll for large insight sets (assume <50 per view)
- Real-time subscription-based updates (initial fetch only)
- Caching strategy (defer to API design, but do not cache beyond session without explicit policy)

## Non-Functional Requirements
- API response time: <2s target (per SARO SLA)
- All insights must carry _traceability metadata (model version, assessment date, audit trail field)
- Logging: log fetch initiated, success/error, response count, and any data validation failures
- Compliance: do not render any insight with missing remediation guidance or confidence score context

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | "AC-1: fetches insights on mount with the current risk context" (AIInsights.test.jsx); "calls /api/v1/insights with bearer token" (insightsService.test.js); TestListInsights.test_risk_id_filter (tests/test_insights_api.py) | frontend/src/pages/AIInsights.jsx, frontend/src/api/insightsService.js, routers/insights.py, services/insights_service.py |
| AC-2 | "AC-2: renders real API fields on the card"; "AC-2: no hardcoded mock data remains"; TestListInsights.test_returns_derived_insights_with_required_fields | frontend/src/pages/AIInsights.jsx, routers/insights.py |
| AC-3 | "AC-3: API error shows an error state with retry"; "AC-3: timeout shows a timeout message"; "aborts after the timeout and flags timedOut" (insightsService.test.js) | frontend/src/pages/AIInsights.jsx, frontend/src/api/insightsService.js |
| AC-4 | "AC-4: a fresh fetch happens on every mount" | frontend/src/pages/AIInsights.jsx |

Edge/NFR: empty-array → "edge: empty array shows the empty state"; no-confidence insights dropped server-side (TestListInsights.test_insight_without_confidence_excluded) and client-side ("drops insights missing confidence context and logs"); `_traceability` metadata (TestListInsights.test_traceability_metadata_present). Backend: `GET /api/v1/insights` (routers/insights.py, migration 021).

---
