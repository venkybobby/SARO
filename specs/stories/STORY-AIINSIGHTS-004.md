# STORY-AIINSIGHTS-004: Add Human Review Framing to AI Suggestions

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
