# STORY-AIINSIGHTS-002: Implement Apply Suggestion Action

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
