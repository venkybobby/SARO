# STORY-CHUB-011 — Validation-Status Filtering for Rule-Pack Data

Epic: Compliance Hub | Priority: P0 (blocks SummitCare demo)
Origin: Regulatory radar scan #1 DB write (2026-07-04) introduced
`validation_status` on `eu_ai_act_rules` and `governance_rules`. 28 rows are
DRAFT_UNVALIDATED and 7 are RETIRED — all currently visible in customer-facing
surfaces because no layer filters on this column.

## User Story
As a Compliance Lead using the Compliance Hub, I must only see SME-validated
rule-pack content in default views, so that SARO never presents unvalidated or
retired regulatory mappings as authoritative — while internal personas can see
and manage draft content explicitly.

## Status Vocabulary (locked by migration radar_scan1_validation_status_columns)
LEGACY_UNREVIEWED | DRAFT_UNVALIDATED | SME_VALIDATED | RETIRED

## Acceptance Criteria

AC-1
Given any customer-facing rule-pack surface (Compliance Hub views, TRACE rule
references, attestation-related displays, exports), When rule data is rendered,
Then rows with validation_status IN ('DRAFT_UNVALIDATED','RETIRED') are
excluded by default.

AC-2
Given the API layer, When any endpoint serves rule-pack data, Then the
status filter is enforced SERVER-SIDE (FastAPI query layer), not only in
React — client-side-only filtering fails closed-review; the API must never
emit draft/retired rows to non-privileged personas.

AC-3
Given an internal/privileged persona (per Persona→Tab Mapping Matrix — owner
to confirm which persona(s) qualify; stop-and-ask if ambiguous), When they
enable a "Show draft content" toggle, Then DRAFT_UNVALIDATED rows render with
a visible DRAFT badge and RETIRED rows with a RETIRED badge; the toggle state
is never persisted as a default.

AC-4
Given LEGACY_UNREVIEWED rows (existing pre-radar content), When rendered,
Then they display in default views (treating legacy as provisionally visible)
but carry a subtle "pending validation" indicator visible only to internal
personas. NOTE: product owner may harden this to excluded-by-default before
SummitCare — implement the treatment behind a single config flag.

AC-5
Given any evaluation/attestation code path that reads rule tables, When rules
are loaded for evaluation, Then DRAFT_UNVALIDATED and RETIRED rules are
excluded from evaluation logic — draft rules must not influence attestations.

AC-6
Given a row transitions to SME_VALIDATED (validated_by + validated_date set),
When views refresh, Then it appears in default views with no badge.

## Edge Cases
- Row with validation_status NULL (future inserts bypassing default): treat as
  DRAFT_UNVALIDATED (fail closed) and log a data-quality warning
- Counts/aggregates (e.g., "41 EU AI Act rules" tiles): must count only
  default-visible rows or label the basis — no mixed-basis numbers
- Export/download paths (CSV, report generation): same server-side filter;
  exports are the easiest leak
- RETIRED framework with zero visible rows (US EO 14110): framework disappears
  from framework selectors entirely rather than showing empty

## Out of Scope
- SME validation workflow itself (evf_sme_engagements integration — separate story)
- Rule-pack version pinning in attestations (separate story, flagged in radar follow-ups)
- Editing/promoting statuses from the UI

## NFRs
- No N+1: status filtering in the base queries, not per-row checks
- Zero regression on Compliance Hub load time budget

## Traceability
| Item | Reference |
|---|---|
| Status columns | Migration radar_scan1_validation_status_columns (Supabase) |
| Draft rows introduced | Migration radar_scan1_rule_pack_delta_data (28 DRAFT, 7 RETIRED) |
| SME validation gate | GRC SME Validation Requirements (claims-before-validation vulnerability) |
| Persona gating | Persona→Tab Mapping Matrix (Epic 9) |
| Evaluation isolation | AC-5 ↔ stateless evaluate-and-attest core invariants |

## Companion task (same PR)
Export both Supabase migrations (radar_scan1_*) into the repo's migration
directory so CI-managed schema_migrations and the live DB do not diverge
(integrated-delivery rule).
> Done: columns migration exported as `migrations/029_radar_scan1_validation_status_columns.sql`
> (in the RPV-001 commit, since RPV-001's gate needed the column); data migration exported as
> `migrations/031_radar_scan1_rule_pack_delta_data.sql` here. Both idempotent.

## Traceability (AC → tests → files)
| AC | Tests | Implementation |
|---|---|---|
| AC-1 DRAFT/RETIRED excluded from default views | `test_default_view_hides_draft_retired_null`, `test_endpoint_default_hides_drafts` | `services/rule_visibility.py`; `get_matrix_rows` filter |
| AC-2 server-side enforcement | `test_endpoint_default_hides_drafts` (+ all service-level tests) | `get_matrix_rows` (single aggregation point for list/coverage/export) |
| AC-3 internal draft toggle for ai_auditor/admin only | `test_privileged_persona_can_show_drafts`, `test_unprivileged_show_drafts_is_ignored` | `routers/compliance_matrix._effective_show_drafts` |
| AC-4 legacy visible behind flag + internal pending badge | `test_legacy_flag_off_hides_legacy`, `test_show_drafts_reveals_all_with_badges` | `config.saro_show_legacy_rules`; `rule_visibility.badge_for` |
| AC-5 draft excluded from evaluation | satisfied by RPV-002 (static crosswalk + published-snapshot pin); no eval code touched | — |
| Edge NULL fail-closed / NIST unaffected / counts exclude drafts | `test_visibility_policy`, `test_nist_rows_always_visible`, `test_coverage_counts_exclude_drafts` | `is_visible_by_default` (allow-list) |
| Companion migrations | applied+verified on Supabase | `migrations/029`, `migrations/031` |
