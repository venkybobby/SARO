STORY-CHUB-005: Compliance Hub headline — overall coverage % + provenance line
Status: ready    Screen/Area: Compliance Hub
Epic: GRC-Compliance-Hub · Priority: P1 · Depends on: STORY-CHUB-001

Goal
`/api/v1/compliance-matrix/coverage` already returns `overall_coverage_pct`, `framework_count`, and `total_rules`, plus a per-framework `last_updated`, but the Compliance Hub displays none of it. The persona's single most useful glance — "how audit-ready am I overall, and as of when" — is missing. Add an overall readiness headline and an "as of" provenance line that auditors expect.

Framework mapping (per ADR-004 scope locks)
- EU AI Act: Article 17 (record provenance — evidence must carry a timestamp).
- NIST AI RMF: MEASURE (aggregate readiness metric).
- ADR-004: the overall % must inherit the same tier-honesty rule — it is labeled "matrix coverage," not "validated compliance."

Acceptance Criteria (Given/When/Then — required before /story will run)
AC-1: Given the coverage response in `frontend/src/pages/ComplianceHub.jsx`, When the page renders, Then a headline shows `overall_coverage_pct`% labeled "Matrix coverage" (not "compliant"/"validated"), with `framework_count` frameworks and `total_rules` rules.
AC-2: Given per-framework `last_updated` values, When the headline renders, Then an "as of {most-recent last_updated}" provenance line is shown next to the overall %.
AC-3: Given coverage data is still loading, When the headline area renders, Then a skeleton placeholder is shown (consistent with the shared `Skeleton` component).
AC-4: Given coverage is unavailable (error), When the headline renders, Then it shows "—" with the existing error note, never a fabricated number.

Edge Cases
- All `last_updated` null → provenance reads "as of —" rather than an invalid date.
- `total_rules = 0` (no matrix rows) → headline shows "No matrix data yet" empty state, not "0% compliant".

Out of Scope
- Changing how `overall_coverage_pct` is computed (backend unchanged).
- Per-framework drill-through (STORY-CHUB-006).

Non-Functional Requirements
- Wording must pass `/saro:compliance-check` scope-lock validation (no overclaiming verbs).

Test Requirements
- Frontend unit (`ComplianceHub.test.jsx`): renders overall %, framework_count, total_rules, and most-recent provenance; null dates → "as of —"; total_rules=0 → empty state; error → "—".

Traceability (filled at close by /story)
AC	Test(s)	Files
AC-1	ComplianceHub.test.jsx "AC-1/AC-2: renders overall %..." + "label says 'Matrix coverage'..."	frontend/src/pages/ComplianceHub.jsx (headline block)
AC-2	ComplianceHub.test.jsx "AC-1/AC-2: ...most-recent provenance" + "all last_updated null → 'as of —'"	frontend/src/pages/ComplianceHub.jsx (mostRecentLastUpdated)
AC-3	ComplianceHub.test.jsx loading covered by Skeleton (data-testid coverage-headline-loading)	frontend/src/pages/ComplianceHub.jsx (Skeleton import)
AC-4	ComplianceHub.test.jsx "AC-4: coverage error → headline shows '—'"	frontend/src/pages/ComplianceHub.jsx (error branch); edge total_rules=0 → "No matrix data yet"
