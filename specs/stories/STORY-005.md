STORY-005: Sample-Level Finding Persistence (S-1101)
Status: ready    Screen/Area: Audit Engine / TRACE

Goal
Persist every Gate-3 sample flag with its matched signal so any finding is reproducible after the run — the primary AI Auditor REJECT-driver. Closes FB-002/025/036.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a batch of 100 samples where exactly 5 contain SSN patterns, When the audit completes and GET /api/v1/traces/{audit_id}/samples?domain=Privacy%20%26%20Security is called, Then exactly 5 SampleFinding records return, each with the matched signal identifier
AC-2: Given a sample containing a full SSN 123-45-6789, When its finding is persisted, Then matched_fragment stores ***-**-**** — the raw SSN never reaches the database
AC-3: Given a batch of 5,000 samples with ~500 flags across 3 domains, When the audit runs, Then it completes in under 10 seconds with zero dropped SampleFinding records
AC-4: Given a user authenticated to Tenant B, When they request Tenant A's sample findings, Then the API returns 403
AC-5: Given a completed audit's AuditTrace risk_domain rows, When detail_json is inspected, Then sample_count and top_sample_ids (max 10) are present
AC-6: Given the TRACE technical mode UI, When a domain is expanded, Then its flagged samples render with signal and redacted fragment

Edge Cases
- Fragment truncation must cut at the PII regex boundary, never mid-pattern (partial SSN is still PII).
- Multiple signals matching one sample: one record per (sample, domain, signal) tuple.
- Empty flag set: zero records, no error.

Out of Scope
- Backfilling historical audits.
- Executive-mode display of sample fragments.

Non-Functional Requirements
Bulk insert in Gate 3 only; p95 audit latency increase under 10% vs baseline. Index on (audit_id, domain). structlog for insert counts.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
AC-6	—	—
