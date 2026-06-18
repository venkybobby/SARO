STORY-TRACE-008: Surface the provenance triple (rule-pack + model version + timestamp)
Status: ready    Screen/Area: TRACE View
Epic: GRC-TRACE-View · Priority: P1 · Depends on: STORY-TRACE-001, STORY-TRACE-003

Goal
Provenance is core to TRACE's defensibility, but today it's a small optional rule-pack badge sourced from `/api/v1/audits/{id}` — which the auditor can't even load (403 until STORY-TRACE-003). The timeline endpoint already returns `model_version`, and the audit report carries `rule_pack_hash`/`rule_pack_version` and `created_at`. Present the full provenance triple — rule-pack hash/version, model version, scan timestamp — as a first-class element so an auditor can cite exactly which engine, rules, and moment produced the verdict.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 13 (transparency), Article 17 (record provenance).
- NIST AI RMF: MEASURE/MANAGE.
- ISO/IEC 42001: document-lifecycle linking (version/provenance lineage).

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given a loaded trace, When the header renders, Then it shows rule-pack version (or short hash), `model_version`, and scan timestamp together as a labeled provenance block.
AC-2: Given `model_version` from the timeline endpoint, When rendered, Then it is displayed (not hidden behind the audit-report fetch alone).
AC-3: Given a provenance field is unavailable, When rendered, Then it shows an explicit "unavailable" / `_PROVENANCE_UNAVAILABLE` style placeholder, never a blank that implies absence of versioning.
AC-4: Given the rule-pack hash, When shown truncated, Then the full hash is available on hover/title for citation.

Edge Cases
- Audit with no rule-pack hash → "provenance unavailable" rather than an empty badge.
- Timestamp rendered in a stable, unambiguous format (with timezone) suitable for an audit file.

Out of Scope
- Changing how provenance is computed/stored.
- Export (STORY-TRACE-006).

Non-Functional Requirements
- Provenance values are read-only and copy-friendly (selectable text / full value in title).

Test Requirements
- Frontend unit (`TraceView.test.jsx`): all three provenance fields render when present; each missing field → "unavailable"; full hash present in title attribute.

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	—	—
AC-2	—	—
AC-3	—	—
AC-4	—	—
