STORY-002: Document Register + Retrospective Claims Audit (S-1002 / Gate G-5)
Status: ready    Screen/Area: Governance Docs

Goal
Create a single source-of-truth register for all governance documents and complete the FR-EVF-17 retrospective claims audit so no two external artifacts contradict each other. Closes FB-007/012/034; performs VERIFY V-2.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the repository, When the V-2 existence check for the GOV-003 DPA and TRC-003 How-SARO-Reasons artifacts runs as the FIRST task, Then presence/absence is recorded in CONCERNS, and absence escalates the documentation scope of STORY-013 and STORY-010 from EVIDENCE to BUILD
AC-2: Given all governance documents, When docs/DOCUMENT_REGISTER.md is created, Then every document has version, date, status, and a supersedes link
AC-3: Given the known contradictions (claims-matrix Gaps 1/3 vs Plan v3 'delivered'; Neon vs Supabase; Railway vs Fly.io), When the register is complete, Then each contradiction is resolved by a superseding entry and a resolved-conflict checklist shows zero open items
AC-4: Given every external-facing artifact, When the retrospective audit per FR-EVF-17 completes, Then each artifact is classified Tier 1/2/3 with a signed-off audit section in docs/evf/retrospective-claims-audit.md

Edge Cases
- Historical documents are superseded, never edited — register points to the authoritative successor.
- If V-2 finds partial artifacts (e.g., draft DPA), classify as Tier 2 'Under Review', not Tier 1.

Out of Scope
- Rewriting historical document content.
- Producing the DPA itself (STORY-013).

Non-Functional Requirements
Standard project rules. Markdown only; no code paths touched.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
