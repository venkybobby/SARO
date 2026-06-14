# STORY-AIINSIGHTS-003: Link Framework Reference to Actual Documentation

**Status:** done — implemented on `story/SARO_AIInsights_Stories` (2026-06-11)
**Screen/Area:** AI Insights / Navigation / Framework Reference

## Goal
"View framework reference" link in each insight navigates to the relevant compliance framework section (e.g., NIST AI RMF, EU AI Act, ISO 42001) so users can validate SARO's reasoning in real-time, or link is removed if no target exists.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given an insight references a framework (e.g., "NIST AI RMF"), When the user clicks "View framework reference", Then they are navigated to the relevant section of the ClaimsMatrix or HowSaroReasons documentation
- AC-2: Given the insight carries a {framework, articleId, sectionId} metadata, When the navigation link is clicked, Then the URL includes anchors or params to deep-link to the exact section (e.g., /docs/nist-rmf#govern-map-impacts)
- AC-3: Given no valid framework target exists for an insight, When the page loads, Then the "View framework reference" link is either hidden or disabled with a tooltip explaining why
- AC-4: Given a user navigates to the framework reference, When they return to AI Insights, Then the insight state is preserved (no data loss)

## Edge Cases
- Framework reference link is malformed or 404 — show error, do not navigate
- User lacks permissions to view the framework documentation — show access denied
- Framework documentation is not yet published — hide link and show "Coming soon" placeholder
- Multiple frameworks referenced in one insight — prioritize primary framework, offer dropdown for others

## Out of Scope
- Generating framework reference documentation (assume it exists in ClaimsMatrix/HowSaroReasons)
- Displaying framework excerpts inline (links only)
- Translating framework content for different languages (out of MVP)

## Non-Functional Requirements
- Link must be labeled with explicit action text: "View [Framework] reference" (not generic "Learn more")
- Navigation must preserve scroll position in AI Insights when user returns (browser back button or explicit return link)
- Logging: log all framework reference clicks with user, insight ID, framework, timestamp
- Compliance: ensure framework links never expose internal SARO reasoning not yet validated by SME (per SARO_GRC_SME_Validation_Requirements)

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | "AC-1/AC-2: clicking the link navigates to the claims matrix section" (AIInsights.test.jsx) | frontend/src/pages/AIInsights.jsx, frontend/src/utils/frameworkLinks.js |
| AC-2 | frameworkLinks.test.js (all mappings, "maps %s to a claims_matrix section") | frontend/src/utils/frameworkLinks.js, frontend/src/pages/ClaimsMatrix.jsx (row anchors + highlight), frontend/src/App.jsx (initialSection) |
| AC-3 | "AC-3: no framework → no reference link rendered"; "AC-3: unmapped framework → disabled link with explanatory tooltip" | frontend/src/pages/AIInsights.jsx |
| AC-4 | Statuses persist server-side (TestInsightAction.test_status_persists_into_listing) and a fresh fetch restores them on return; scroll position restored via module-scoped save (handleViewFramework/load) | frontend/src/pages/AIInsights.jsx, routers/insights.py |

NFR: explicit "View [Framework] reference" labels ("labels use explicit action text", frameworkLinks.test.js); clicks logged with user/insight/framework/timestamp (handleViewFramework). Insights only ever link to the Claims Matrix (validated claims), never internal reasoning (SME validation requirement).

---
