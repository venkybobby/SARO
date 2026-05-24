# Skill: SARO Compliance Context

These are the locked compliance scope definitions for SARO v8.0. Do not expand, reinterpret, or upgrade these without explicit instruction.

## NIST AI RMF 1.0

- Self-assessment artefact: `SARO_NIST_RMF_SelfAssessment_v1.0`
- Coverage: GOVERN, MAP, MEASURE, MANAGE functions
- SARO's role: evidence collection and workflow support — not a certification tool
- When generating compliance outputs, frame as "evidence support" not "certification"

## EU AI Act

- Scope is **Articles 9, 13, 17 only**
  - Article 9: Risk management system documentation support
  - Article 13: Transparency and information provision support
  - Article 17: Quality management system evidence linking
- Do NOT claim or imply coverage of other EU AI Act articles
- Frame all EU AI Act outputs as "evidence support for Articles 9, 13, 17"

## ISO 42001

- Scoped as **lightweight document lifecycle linking only**
- SARO supports document traceability and version tracking aligned to ISO 42001 structure
- Do NOT position as full ISO 42001 certification support

## AIGP (AI Governance Professional)

- Described as **"principles evaluation" only**
- AIGP alignment outputs = principles-level assessment, not audit-ready compliance
- Do not describe AIGP outputs as audit evidence or certifiable compliance

## Critical Gates Before External Sharing / Enterprise Demo

The following three gaps must be closed before any external sharing of SARO capabilities:
1. **Incident Response Plan** — not yet complete
2. **External Compliance SME engagement** — rule pack editorial review required
3. **Data Retention / DPA Policy** — not yet complete

Flag these proactively if a task touches external sharing, demo prep, or enterprise buyer materials.

## TRACE View

- Alex Rivera (ML Lead) must author the "How SARO Reasons" transparency document **before** any enterprise demo of the TRACE view
- Do not produce TRACE demo scripts or materials until this document exists

## Compliance Engines (Core)

| Engine | Function |
|--------|----------|
| Drift Sentinel | Kafka KS-Test, Circuit Breaker pattern, ISO 42001 alignment |
| SEC Proof | 22-field AuditRecord, SHA256 chain, SEC Rule 17a-4 |
| eKYC Shield | 4-layer injection detection, FAR 0.01% target |
| Fairness/SHAP | Disparate Impact Ratio, SHAP explainability, ISO 24027/NIST AI 100-1 |

## Verticals

Finance, Healthcare, Technology, Government

## User Personas

| Persona | Role |
|---------|------|
| Forecaster | Predicts compliance risk |
| Autopsier | Post-incident analysis |
| Enabler | Workflow automation |
| Evangelist | Stakeholder reporting |
