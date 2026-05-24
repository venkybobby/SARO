# RB-005: Enterprise Demo Pre-Flight Checklist

**Owner:** Venky R  
**Use when:** Preparing for any enterprise prospect or investor demo of SARO  
**Time required:** ~2 hours for full checklist

---

## Step 1 — Critical Gaps Status Check (MUST COMPLETE FIRST)

Run `/saro:compliance-check` and verify all three gaps are closed:

- [ ] **Incident Response Plan** — complete and reviewed?
- [ ] **External Compliance SME** — rule pack editorial review complete?
- [ ] **Data Retention / DPA Policy** — complete and reviewed?

> ⛔ If ANY gap is open: do not proceed to external demo. Internal demo only.

---

## Step 2 — TRACE View Gate

- [ ] Alex Rivera's "How SARO Reasons" document exists and is current version?
- [ ] Alex has reviewed the TRACE demo script?

> ⛔ If TRACE is in the demo and Alex's doc doesn't exist: remove TRACE from demo scope.

---

## Step 3 — Compliance Claims Audit

Run `/saro:compliance-check` on the demo script. Verify:

- [ ] EU AI Act claims limited to Articles 9, 13, 17 only
- [ ] ISO 42001 described as document lifecycle linking — no certification claims
- [ ] AIGP described as principles evaluation — not audit evidence
- [ ] NIST AI RMF described as evidence support — not certification
- [ ] All outputs framed as "evidence support" not "certified compliance"

---

## Step 4 — Technical Readiness

- [ ] Latest Koyeb build is healthy — health endpoint returns `{"version": "8.0.0", "status": "healthy"}`
- [ ] Demo dataset loaded (real fixture data — not mocked)
- [ ] All four verticals functional: Finance, Healthcare, Technology, Government
- [ ] Drift Sentinel: can trigger a demo drift event cleanly
- [ ] TRACE view: renders SHAP scores correctly for Finance vertical
- [ ] Report generation: Claude API producing compliance report prose
- [ ] Performance: TRACE p95 < 500ms (run a quick Locust spot check)

---

## Step 5 — Persona Matching

Identify the buyer persona attending:

| Persona | Focus areas in demo |
|---------|-------------------|
| Compliance Lead | NIST AI RMF evidence, audit trail, Article 9/17 support |
| Risk Officer | Drift Sentinel, circuit breaker, incident response |
| AI Auditor | TRACE view, SHAP scores, SEC Proof audit chain |

---

## Step 6 — Post-Demo

- [ ] Do not leave demo environment running with real data
- [ ] Any compliance evidence generated during demo — mark as `demo_artifact: true` in Neon
- [ ] Follow-up materials reviewed against scope locks before sending

---

## Emergency Rollback (if demo breaks)

```powershell
# In Koyeb dashboard — redeploy previous build
# Or via CLI:
koyeb service redeploy saro-platform --deployment <previous-deployment-id>
```

Contact Jordan Lee immediately if DB issues during demo.
