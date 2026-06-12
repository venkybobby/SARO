STORY-001: Citation Accuracy Fix (S-1104 / Gate G-4)
Status: ready    Screen/Area: Audit Engine / Gate 1 + Compliance Docs

Goal
Remove the incorrect EU AI Act Art. 10 / NIST MAP 2.3 attribution from the 50-sample minimum so no framework citation in SARO is factually wrong. Closes FB-015/035.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a batch of 30 samples, When POST /api/v1/scan is submitted, Then the 422 response body contains no string 'EU AI Act Art. 10' in the minimum-sample context
AC-2: Given the full repository, When grep -r 'EU AI Act Art. 10' runs, Then zero matches exist in Gate-1 minimum-sample contexts while legitimate Gate-4 data-governance mappings (ART_10, ART_10_3) remain byte-identical
AC-3: Given the Gate-1 fail message, BatchIn/SARoDataBatchIn docstrings, and gate_id=1 remediation hint, When they are rendered, Then each cites 'internal SARO statistical methodology' language, not a regulatory article
AC-4: Given docs/compliance-claims.md, When the new 'Sampling Methodology Basis' section is reviewed, Then it documents the statistical rationale for the 50-sample threshold with independently verifiable citations

Edge Cases
- A compliance officer reviewing the matrix can map every remaining citation to actual regulatory text.
- Error-message change must not alter Gate-1 pass/fail behavior (regression: ENG-001 still fails a 49-sample batch).

Out of Scope
- Full citation audit across all rule packs — SME scope in STORY-004.
- Any change to gate thresholds or logic.

Non-Functional Requirements
Standard project rules. No behavioral change to the engine; text and docs only. CI green required.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
