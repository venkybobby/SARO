# Command: /saro:phase-gate-review

Run a hard gate review for Phase 0 (Requirements & Compliance Scoping) or Phase 3 (QA & Security Review).

## Usage

```
/saro:phase-gate-review [phase-0 | phase-3] [epic or feature name]
```

Example: `/saro:phase-gate-review phase-3 "Drift Sentinel v2"`

---

## Phase 0 Hard Gate Checklist

Do NOT proceed to development until all items are checked.

**Requirements**
- [ ] Problem statement is scoped to a single vertical or cross-vertical with explicit boundaries
- [ ] Functional requirements written in FR-XXX format
- [ ] Non-functional requirements written in NFR-XXX format
- [ ] Acceptance criteria defined for each FR

**Compliance Scoping**
- [ ] NIST AI RMF functions identified (GOVERN / MAP / MEASURE / MANAGE)
- [ ] EU AI Act scope confirmed as Articles 9, 13, 17 only — no other articles claimed
- [ ] ISO 42001 positioned as document lifecycle linking — no certification claims
- [ ] AIGP positioned as principles evaluation — no audit evidence claims
- [ ] No out-of-scope compliance claims detected

**Critical Gaps Check**
- [ ] If this feature touches external sharing: Incident Response Plan status confirmed
- [ ] If this feature touches external sharing: SME review status confirmed
- [ ] If this feature touches external sharing: DPA Policy status confirmed

**TRACE Gate**
- [ ] If TRACE view involved: Alex Rivera's "How SARO Reasons" doc confirmed complete

**Team Alignment**
- [ ] Venky signed off on scope
- [ ] Jordan Lee reviewed technical feasibility
- [ ] Alex Rivera reviewed ML components (if applicable)

---

## Phase 3 Hard Gate Checklist

Do NOT proceed to staging until all items are checked.

**Test Coverage**
- [ ] All new FRs have passing unit tests
- [ ] Integration tests passing
- [ ] E2E Playwright tests passing (if UI changed)
- [ ] Performance baseline met: p95 < 500ms at 50 concurrent users

**Security**
- [ ] OWASP scan clean — no P0/P1 findings open
- [ ] No hardcoded secrets in new code
- [ ] JWT auth on all new endpoints
- [ ] No blocking async patterns introduced

**QA Sign-off**
- [ ] Sam Patel sign-off
- [ ] Taylor Kim sign-off

**Compliance Evidence**
- [ ] Audit trail entries generated for new compliance events
- [ ] Version string is 8.0.0 — no drift introduced

**Deployment Readiness**
- [ ] Koyeb deployment config updated if needed
- [ ] Neon migration scripts tested against staging DB
- [ ] Redis session patterns follow patched async pattern

---

## Output Format

```
PHASE [0|3] GATE REVIEW — [Epic/Feature Name]
==============================================
Gate: PASS ✅ / FAIL ❌ / CONDITIONAL ⚠️

PASSED ITEMS: [count]
FAILED ITEMS: [list each with action owner]
BLOCKED BY: [list hard blockers]

RECOMMENDATION: [PROCEED / HOLD — reason]
```
