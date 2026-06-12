STORY-006: Engine and Rule-Pack Provenance (S-1102)
Status: ready    Screen/Area: Audit Engine / Reports

Goal
Stamp every report with the engine version and rule-pack hash that produced it so historical evidence is attributable and tamper-evident. Ships with STORY-005 as one release (FB-036). Closes FB-003/025.

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a completed ScanReport, When it is retrieved, Then engine_version (matching CLAUDE.md), rule_pack_hash, and compliance_matrix_version are non-null
AC-2: Given a simulated single-keyword change in _RISK_SIGNALS, When GET /api/v1/engine/integrity is called, Then the rule_pack_hash differs from the pre-change value and the change history lists it
AC-3: Given the same batch audited before and after a rule-pack change, When the second report is generated, Then rule_change_warning is true and lists the affected domains
AC-4: Given an EnhancedTrace export, When either trace content or engine version changes, Then export_hash changes
AC-5: Given the TRACE view, When any audit is opened, Then the footer renders the provenance line

Edge Cases
- Hash must be deterministic: canonical JSON serialization (sorted keys) of _RISK_SIGNALS + _COMPLIANCE_TRIGGERS.
- engine_versions history table is append-only — no UPDATE path.

Out of Scope
- Signing keys / HSM.
- RFC 3161 timestamping (AUD-003 stays parked).

Non-Functional Requirements
Integrity endpoint read-only, rate-limit friendly. Hash computation cached per process start.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
AC-5	—	—
