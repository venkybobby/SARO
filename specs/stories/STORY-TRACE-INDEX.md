SARO — TRACE View Story Pack (TRACE-001..010)
Screen: frontend/src/pages/TraceView.jsx
Code-grounded review of TraceView.jsx + routers/traces.py, routers/trace_view.py,
routers/scan.py, services/trace_service.py, ADR-004.

USAGE
Drop these .md files into specs/stories/, then run /story TRACE-00X.
Each file satisfies the Definition of Ready gate (Given/When/Then ACs + Edge Cases
+ Out of Scope) and respects ADR-004 scope locks (EU AI Act Arts 9/13/17 only;
AIGP principles only; ISO 42001 doc-lifecycle linking only).

PRIORITY MAP
P0 — correctness, security & positioning (before any auditor/enterprise demo)
  TRACE-001  Repoint to /api/v1/audit/{id}/trace + normalize render contract + truthful step status   [needs 002]
  TRACE-002  Tenant-scope the timeline endpoint (cross-tenant leak)        [SECURITY — do first]
  TRACE-003  AI Auditor read access to traces/audit-detail/audits list     [SECURITY]
  TRACE-004  Honest integrity banner (verify real signature or remove)     [needs 001]
  TRACE-005  Enforce ADR-004 TRACE gate (How SARO Reasons link + demo gate)

P1 — usable evidence tool
  TRACE-006  Signed export actions (JSON + PDF)                            [needs 002, 003]
  TRACE-007  Recent Traces role + overall_risk_score field                [needs 003]
  TRACE-008  Provenance triple (rule-pack + model_version + timestamp)     [needs 001, 003]

P2 — consistency & polish
  TRACE-009  Refactor onto shared design system                           [needs 001]
  TRACE-010  Loading skeletons + differentiated 403/404/network errors     [needs 009]

RECOMMENDED EXECUTION ORDER
1. TRACE-002  (security; unblocks the repoint safely)
2. TRACE-003  (security; unlocks the auditor persona)
3. TRACE-001  (make the screen actually render the truth)
4. TRACE-004  (stop the unbacked integrity claim)
5. TRACE-005  (ADR-004 gate)
6. TRACE-008, TRACE-007, TRACE-006  (evidence-tool value)
7. TRACE-009 → TRACE-010  (presentation)

SECURITY-AUDITOR REVIEW REQUIRED (per /story step 5)
  TRACE-002, TRACE-003

OVERLAP WITH COMPLIANCE HUB PACK — DO NOT DOUBLE-BUILD
  TRACE-003 is a superset of CHUB-002 (audits-list role gate). If CHUB-002 is
    already merged, only the trace + audit-detail gates remain in TRACE-003.
  TRACE-007 shares the overall_risk_score fix with CHUB-003, but in a different
    file (TraceView.jsx vs ComplianceHub.jsx) — both copies must be fixed.
  Tenant-scoping pattern in TRACE-002 mirrors CHUB-010 / STORY-015; reuse the
    same isolation test harness.

KEY EVIDENCE BEHIND THIS PACK
- UI calls /api/v1/traces/{id} → returns list[AuditTraceOut] (array), rendered as an object
  → status always PENDING, risk chip blank, all-green strip (steps_completed || 6),
  no detail panels, no integrity banner.
- Correct endpoint is /api/v1/audit/{id}/trace (trace_view.py:48 → build_trace_timeline),
  but it returns steps as an ARRAY of {key,status,detail,rules_fired} (trace_service.py:110)
  and is NOT tenant-scoped (_get_audit_or_404(db, audit_uuid) — no tenant filter).
- /traces/{id} and /audits/{id} gated super_admin/operator → ai_auditor & compliance_lead get 403.
- Integrity claim reads trace.hash_chain_valid (absent); real signal is HMAC _signature/export_hash (trace_view.py:135).
- ADR-004 requires "How SARO Reasons" before enterprise TRACE demo; HowSaroReasons.jsx exists but is unlinked/ungated.
- Recent Traces uses /api/v1/audits (role-gated) + reads a.risk_score (field is overall_risk_score).
- Export endpoints exist (/export/json, /export/pdf) but no UI entry point.
