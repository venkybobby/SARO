STORY-014: Incident Corpus Transparency (S-1106)
Status: ready    Screen/Area: Risk Dashboard / Reports

Goal
Expose corpus statistics and a similarity floor so meaningful incident matches are distinguishable from noise, and make is_fixed auditable. Closes FB-018/019.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given GET /api/v1/reports/incident-corpus-stats, When it is called with a populated ai_incidents table, Then total count, by-category, by-harm-type, date range, percent fixed, and last-update fields all return
AC-2: Given a scan whose text has no meaningful incident overlap, When similar incidents are returned, Then every match with similarity_score below the threshold (default 0.15, configurable via AuditConfigIn) carries low_confidence: true
AC-3: Given an incident record update, When the next audit of the same batch runs, Then the report's incident_corpus_version reflects the change
AC-4: Given any change to is_fixed, When it is persisted, Then fixed_by and fixed_at are written in the same transaction
AC-5: Given the risk dashboard, When it renders, Then the corpus stats card displays

Edge Cases
- Empty corpus: stats endpoint returns zeros, similarity returns empty list, no crash (ENG-007 regression).
- Threshold set to 0 by caller: low_confidence never true — document that 0 disables the floor.

Out of Scope
- Corpus content expansion or curation.
- Changing the 200-sample TF-IDF concatenation cap (document it instead in S-1103 methodology doc).

Non-Functional Requirements
Stats endpoint cached 5 minutes. Migration transactional with rollback comment.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
