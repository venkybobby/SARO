SARO — Compliance Hub Story Pack (CHUB-001..010)
Screen: frontend/src/pages/ComplianceHub.jsx
Generated from a code-grounded review of ComplianceHub.jsx + backing endpoints
(routers/scan.py, routers/compliance_matrix.py, routers/evf_sprint3.py,
services/evf_validation_status_service.py, routers/risk_dashboard.py).

USAGE
Drop these .md files into specs/stories/, then run /story CHUB-00X.
Each file satisfies the Definition of Ready gate (Given/When/Then ACs + Edge Cases
+ Out of Scope) and respects ADR-004 scope locks (EU AI Act Arts 9/13/17 only;
AIGP principles only; ISO 42001 doc-lifecycle linking only).

PRIORITY MAP
P0 — correctness & positioning (do before any compliance_lead demo)
  CHUB-001  EVF Validation Status card → real tier data, fix name key, tier-with-coverage invariant
  CHUB-002  Recent Audits → grant compliance_lead read access (fix 403 role gate)
  CHUB-003  Recent Audits → fix risk-score field mapping (always "—" bug)   [after 002]

P1 — make it a workspace
  CHUB-004  Readiness Checklist → persist per tenant, back with real status
  CHUB-005  Headline → overall coverage % + "as of" provenance              [after 001]
  CHUB-006  Actions → export CSV, board report, framework/audit drill-through [after 001,002]

P2 — consistency & polish
  CHUB-007  Refactor onto shared design system (PageHeader/tokens/Card/Skeleton)
  CHUB-008  Loading skeletons + visible error states                        [after 007]
  CHUB-009  Remove/wire dead params (window/sort/tenant_id)
  CHUB-010  Verify tenant scoping on /coverage and /validation-status (security)

RECOMMENDED EXECUTION ORDER
1. CHUB-001  (highest risk: anti-overclaiming, ADR-004)
2. CHUB-002 → CHUB-003  (unblocks the Recent Audits table end-to-end)
3. CHUB-010  (security; cheap to run early, de-risks 005/006 data trust)
4. CHUB-005, CHUB-006  (workspace value, depend on 001/002)
5. CHUB-004  (new endpoint + store; larger)
6. CHUB-007 → CHUB-008  (presentation; do together)
7. CHUB-009  (cleanup)

SECURITY-AUDITOR REVIEW REQUIRED (per /story step 5 — touches routers/ or access)
  CHUB-002, CHUB-004, CHUB-010

KEY EVIDENCE BEHIND THIS PACK
- /api/v1/audits gated require_role("super_admin","operator","demo_viewer") → excludes compliance_lead (scan.py:329)
- /audits returns overall_risk_score; UI reads a.risk_score → always "—"
- /compliance-matrix/coverage returns key `framework` (UI reads fw.name) and no EVF fields (UI reads fw.evf_tier) → blank names, no tier badge
- Real tier data lives at /api/v1/evf/validation-status, uncalled by the EVF card
- Readiness checklist is in-memory useState, hardcoded list → never persists
- overall_coverage_pct returned by /coverage but never displayed
- /compliance-matrix/export (CSV) and /risk/board-export (PDF) exist but have no UI entry point
