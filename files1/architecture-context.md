# Skill: SARO Architecture Context

## MVP Roadmap

| MVP | Name | Status |
|-----|------|--------|
| MVP1 | Ingestion & Forecast | Complete |
| MVP2 | Compliance Engines | Complete |
| MVP3 | Reporting & TRACE | Complete |
| MVP4 | Agentic Guardrails & Commercial GA | In Progress |

## Current State: v8.0 — Enterprise Production Readiness Phase

SARO is deployed and functional. The current focus is enterprise-grade production readiness and commercial viability.

## SDLC Navigator (8 Phases)

Hard gates at **Phase 0** and **Phase 3** — do not proceed past these without explicit sign-off.

| Phase | Name | Hard Gate |
|-------|------|-----------|
| 0 | Requirements & Compliance Scoping | ✅ HARD GATE |
| 1 | Architecture Design | — |
| 2 | Development | — |
| 3 | QA & Security Review | ✅ HARD GATE |
| 4 | Compliance Evidence Assembly | — |
| 5 | Staging Deploy | — |
| 6 | Enterprise Demo Readiness | — |
| 7 | Commercial GA | — |

## Enterprise Buyer Personas

| Persona | Title | Primary Pain |
|---------|-------|-------------|
| Compliance Lead | Chief Compliance Officer / VP Compliance | Regulatory evidence gaps, audit readiness |
| Risk Officer | Chief Risk Officer / VP Risk | Model risk, drift detection, incident response |
| AI Auditor | Internal/External AI Auditor | Explainability, audit trails, TRACE view |

## Key Artefacts (Produced)

- `SARO_NIST_RMF_SelfAssessment_v1.0` — NIST AI RMF 1.0 self-assessment
- 9-slide executive strategy presentation
- Three enterprise buyer persona briefs
- 8-phase SDLC Navigator with hard gates
- CLAUDE.md, README.md, ARCHITECTURE.md, CONTRIBUTING.md

## Test Framework

- 180 tests across: unit, integration, E2E (Playwright), performance (Locust), security (OWASP)
- 35+ fixture files
- Functional requirements coverage: FR-001 through FR-018
- Non-functional requirements: NFR-001 through NFR-007
- Real ML model outputs in test data (no mocked predictions)

## Five Enhancement Stories (Spec'd & Tested)

1. Onboarding with Redis/RDS sync
2. Selective EU AI Act Article 12 action logging
3. GDPR 6-month purge
4. Claude API-generated compliance reports
5. Multi-role with AI role auto-suggestion
