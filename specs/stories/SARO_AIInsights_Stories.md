# STORY-001: Wire AI Insights to Backend Data Service

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

# STORY-002: Implement Apply Suggestion Action

**Status:** done — implemented on `story/SARO_AIInsights_Stories` (2026-06-11)
**Screen/Area:** AI Insights / Suggestion Actions

## Goal
User can apply an AI suggestion to a risk, triggering a clear, trackable action (either navigate to risk detail for manual remediation or auto-create a remediation task) with confirmation and audit trail.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given an insight is displayed in InsightCard, When the user clicks "Apply suggestion", Then the app navigates to /risk/{riskId}/detail with a query param ?suggested_remediation={remediationId} or equivalent
- AC-2: Given a user arrives at risk detail with ?suggested_remediation param, When the page loads, Then the recommended remediation is pre-filled in the remediation form or highlighted visually
- AC-3: Given the user applies the suggestion, When they confirm, Then the backend records an audit event: {user, action: "applied_suggestion", insightId, riskId, timestamp}
- AC-4: Given the suggestion has been applied, When the user returns to AI Insights, Then the insight status updates to "accepted" and a confirmation message is shown (e.g., "Remediation applied to Risk-123")

## Edge Cases
- Risk does not exist (deleted before action) — show error, do not create orphaned remediation
- User lacks permission to edit the risk — show access denied message, not generic error
- Suggestion contains invalid remediation data — show validation error, do not navigate
- Multiple users apply the same suggestion in parallel — handle gracefully (last write wins, or lock)

## Out of Scope
- Auto-creating remediation tasks without user confirmation (must be explicit)
- Bulk apply (applying same suggestion to multiple risks at once)
- Undo/rollback of applied suggestions (out of MVP scope)

## Non-Functional Requirements
- Audit trail: every apply action must be logged with user, timestamp, insight version, and risk state pre/post
- UX: action must complete within 2s or show a loading spinner with clear messaging
- Accessibility: "Apply suggestion" button must be labeled with context (e.g., "Apply suggestion: <remediation summary>")
- Logging: log apply action, navigation, confirmation, and any backend errors

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | "AC-1: confirming navigates to risk detail with the suggested remediation" | frontend/src/pages/AIInsights.jsx, frontend/src/App.jsx (risk_detail wiring, FND-007) |
| AC-2 | "opens the Remediation tab and highlights the suggestion" (RiskDetail.test.jsx) | frontend/src/pages/RiskDetail.jsx |
| AC-3 | TestInsightAction.test_apply_records_audit_event (tests/test_insights_api.py); "AC-3: the action posts with human-review acknowledgement" | routers/insights.py (AuditEvent row), frontend/src/api/insightsService.js |
| AC-4 | "AC-4: status flips to accepted and a confirmation message shows"; TestInsightAction.test_status_persists_into_listing | frontend/src/pages/AIInsights.jsx, routers/insights.py, models.py (InsightAction), migrations/021_create_insight_actions.sql |

Edge: deleted risk → TestInsightAction.test_unknown_insight_404 + "edge: deleted risk (404)…"; permission → TestInsightAction.test_read_only_persona_403 + "edge: permission denied (403)…"; parallel applies → TestInsightAction.test_repeat_action_last_write_wins (last write wins). Navigation adapted to the app's state-based `onNavigate("risk_detail", payload)` — no URL routing exists for pages.

---

# STORY-003: Link Framework Reference to Actual Documentation

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

# STORY-004: Add Human Review Framing to AI Suggestions

**Status:** done — implemented on `story/SARO_AIInsights_Stories` (2026-06-11)
**Screen/Area:** AI Insights / Compliance Messaging

## Goal
Each AI suggestion carries a compliance-required disclaimer ("Recommended remediation — human validation required") at point of action, aligned with COMPLIANCE_CLAIMS_MATRIX.md and matching the framing already used in RiskDetail.jsx, to ensure users do not treat SARO suggestions as final recommendations.

## Acceptance Criteria (Given/When/Then — required before /story will run)
- AC-1: Given an insight is displayed in InsightCard, When the user views the card, Then a disclaimer line is visible near the action buttons: "Recommended remediation — human validation required"
- AC-2: Given the user hovers over or clicks the disclaimer, When they interact with it, Then a tooltip or inline message explains why human review is needed (e.g., "SARO recommendations support risk assessment but require compliance review before deployment")
- AC-3: Given the user is about to apply a suggestion, When they click "Apply suggestion", Then a confirmation dialog appears restating the human review requirement
- AC-4: Given the insight carries a high confidence score (>90%), When the user views the suggestion, Then the disclaimer is NOT removed or de-emphasized—it remains equally prominent

## Edge Cases
- Insight has no remediation guidance (only flags a risk) — reframe to "Human review required: no automated remediation available"
- User is in "read-only" mode (auditor view) — disclaimer is still shown, but "Apply" button is disabled
- Very long remediation descriptions — ensure disclaimer is not pushed off-screen or hidden
- Multiple languages — ensure disclaimer is translated and maintains legal accuracy

## Out of Scope
- Changing the compliance requirements themselves (this is policy, not product)
- Requiring SME pre-approval before suggestions are shown (that is STORY-001 + compliance validation layer, not UI)
- Analytics on how many users skip or ignore the disclaimer (defer to product analytics phase)

## Non-Functional Requirements
- Disclaimer must use exact wording from COMPLIANCE_CLAIMS_MATRIX.md to ensure consistency
- Styling: disclaimer must use warning or neutral color (not green/success) to avoid false confidence
- Accessibility: disclaimer text must be readable by screen readers and have sufficient color contrast (WCAG AA+)
- Logging: log every suggestion view and apply action with user, time, whether disclaimer was shown
- Compliance: audit trail must include timestamp of disclaimer presentation

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | "AC-1: the exact ClaimsMatrix disclaimer appears on every card with remediation" | frontend/src/pages/AIInsights.jsx (HumanReviewDisclaimer) |
| AC-2 | "AC-2: the explainer is available on interaction" | frontend/src/pages/AIInsights.jsx |
| AC-3 | "AC-3: applying opens a confirmation restating the requirement"; backend enforcement TestInsightAction.test_apply_without_human_review_ack_rejected | frontend/src/pages/AIInsights.jsx (ConfirmDialog), schemas.py (InsightActionIn) |
| AC-4 | "AC-4: disclaimer is equally present at >90% confidence" | frontend/src/pages/AIInsights.jsx |

Edge: no-remediation reframe ("edge: insights without remediation reframe the disclaimer"); read-only auditor ("edge: read-only auditor persona sees the disclaimer but cannot act" + TestInsightAction.test_read_only_persona_403). NFR: exact COMPLIANCE_CLAIMS_MATRIX wording (DISCLAIMER_TEXT constant), warning color (var(--color-medium), never green), audit trail records human_review_acknowledged (TestInsightAction.test_apply_records_audit_event). i18n out of scope — no i18n infrastructure exists.

---

# STORY-005: Tie AI Loading State to Real Data Fetch

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

# STORY-006: Optimize Filter Tab Discoverability

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
