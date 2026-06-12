# STORY-112: Consolidate Governance Tabs into a Single Trust Center
Status: draft
Screen/Area: UI Architecture / Compliance Hub, Claims Matrix, Governance Trust, DPA & Governance, EVF Status (+ AIMS placement decision)

## Goal
Six surfaces answer overlapping versions of "can I trust this vendor/evidence?" Merge into one Trust Center page with sections (Claims, Governance Docs & DPA, EVF Status, Compliance Hub content), shrinking the validation surface the EVF must defend while making the trust narrative coherent for the Compliance Lead and AI Auditor personas.

GRC mapping: every retired surface is one fewer page the EVF must validate and an auditor may interrogate; ISO/IEC 42001 A.8 information coherence.

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the IA design, When approved by the product owner (pre-execution alignment step — this is a structural change), Then a one-page section map shows where each existing tab's content lands, with nothing silently dropped.
- AC-2: Given the Trust Center ships, When a user visits any retired tab's route, Then they are redirected to the corresponding Trust Center section anchor.
- AC-3: Given persona mappings, When updated, Then compliance_lead and ai_auditor (post-STORY-109) see the Trust Center, and per-persona section visibility matches what each could see before — no accidental privilege expansion or loss.
- AC-4: Given the regression suite, When run, Then every piece of functional behavior from the merged tabs (claims table, doc downloads, EVF status indicators, DPA artifacts) has a passing test against the new location.
- AC-5: Given the Persona→Tab Mapping Matrix and nav config, When inspected, Then the five retired tabs are removed and total page count reflects the consolidation.

## Edge Cases
- AIMS evidence packs: decide explicitly whether AIMS joins the Trust Center or remains standalone — record as ADR either way.
- External links/demo scripts pointing at retired routes → redirect coverage test.
- Section-level RBAC differences (e.g., DPA visible to fewer personas than Claims) → Trust Center must support per-section visibility.

## Out of Scope
- New trust content; risk-cluster merge (STORY-113); visual redesign beyond layout needed for sections.

## Non-Functional Requirements
- No regression in page-load performance vs. heaviest retired tab; audit logging preserved per section. Standard project rules.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
