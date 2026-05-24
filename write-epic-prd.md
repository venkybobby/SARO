# Command: /saro:write-epic-prd

Write a SARO Epic PRD in Word document format following the established four-epic structure.

## Usage

```
/saro:write-epic-prd [epic-name] [brief description]
```

Example: `/saro:write-epic-prd "Drift Sentinel v2" "Add CUSUM test alongside KS-Test for financial model drift"`

## Output Format (Word .docx)

Produce a structured Epic PRD with these sections:

### 1. Epic Overview
- Epic ID and Name
- Target MVP phase
- Product Owner: Venky R
- ML Lead: Alex Rivera
- Backend Lead: Jordan Lee
- QA: Sam Patel, Taylor Kim

### 2. Business Context
- Problem statement
- Affected verticals (Finance / Healthcare / Technology / Government)
- Affected personas (Forecaster / Autopsier / Enabler / Evangelist)

### 3. Compliance Alignment
- NIST AI RMF functions impacted (GOVERN / MAP / MEASURE / MANAGE)
- EU AI Act articles impacted (Articles 9, 13, 17 only — no others)
- ISO 42001 document lifecycle links (lightweight only)
- AIGP principles alignment (principles evaluation only — not audit evidence)

### 4. Functional Requirements
- FR-XXX format, sequenced from last assigned FR ID
- Each FR: ID, description, acceptance criteria, test reference

### 5. Non-Functional Requirements
- NFR-XXX format
- Performance, security, compliance, reliability targets

### 6. Technical Design Notes
- API changes (show endpoint signatures only)
- DB schema changes (migration notes)
- Async/concurrency considerations
- Koyeb/Neon deployment impact

### 7. Test Plan
- Unit, integration, E2E, performance, security coverage
- Locust scenario if performance-impacting
- Playwright scenario if UI-impacting

### 8. SDLC Phase Gate Checklist
- Phase 0 hard gate criteria for this epic
- Phase 3 hard gate criteria for this epic

### 9. Open Questions / Risks

## Rules
- Flag if the epic touches TRACE view (Alex's transparency doc required first)
- Flag if the epic touches external sharing or demo materials (3 critical gaps check)
- Version references: always 8.0.0
