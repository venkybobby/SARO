# Command: /saro:trace-review

Run a pre-demo readiness check for the SARO TRACE view (AI reasoning transparency feature).

## Usage

```
/saro:trace-review [demo target: internal | enterprise-prospect | investor]
```

Example: `/saro:trace-review enterprise-prospect`

## What This Command Checks

### Hard Blocker (Non-Negotiable)

> **Alex Rivera must have authored and published "How SARO Reasons" before any TRACE demo to an external audience.**

If this document does not exist: **BLOCKED. Do not proceed.**

### TRACE View Readiness Checklist

**Documentation**
- [ ] "How SARO Reasons" document authored by Alex Rivera — exists and reviewed?
- [ ] Document version matches current SARO version (8.0.0)?
- [ ] SHAP explainability methodology documented?
- [ ] Disparate Impact Ratio explanation included?

**Demo Data**
- [ ] Demo dataset uses real ML fixture data (not random mocks)?
- [ ] Finance vertical: GradientBoostingClassifier output visible in TRACE?
- [ ] Healthcare vertical: RandomForestClassifier output visible in TRACE?
- [ ] NIST AI RMF assessment linkage shown in TRACE?

**Compliance Claims in Demo**
- [ ] TRACE framed as "evidence support" — not as certification?
- [ ] EU AI Act Article 13 (transparency) cited correctly — no other articles?
- [ ] AIGP framed as principles evaluation — not audit evidence?

**Critical Gaps (if external audience)**
- [ ] Incident Response Plan complete? (if NO — do not demo to external)
- [ ] SME review complete? (if NO — flag to audience or do not demo)
- [ ] DPA Policy complete? (if NO — do not demo to external)

**Technical**
- [ ] TRACE endpoint p95 < 500ms?
- [ ] TRACE view renders correctly on latest Koyeb build?

## Output Format

```
TRACE DEMO READINESS REPORT
============================
Target Audience: [internal | enterprise-prospect | investor]
Date: [date]

HARD BLOCKER:
  Alex Rivera "How SARO Reasons" doc: [EXISTS ✅ / MISSING ❌ — DEMO BLOCKED]

CHECKLIST SUMMARY:
  Passed: [count]
  Failed: [list]

CRITICAL GAPS:
  [status of all three]

VERDICT: [READY TO DEMO ✅ / BLOCKED ❌ — reasons]
```
