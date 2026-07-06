# STORY-CHUB-011 — Validation-Status Filtering for Rule-Pack Data
Stage: standard

## Lifecycle
- [x] discover   (recon: get_matrix_rows (services/compliance_matrix_service.py) is the SINGLE
                  aggregation point feeding GET /compliance-matrix, /coverage (counts), /export (CSV);
                  governance_rules NOT served to any customer surface; NIST has no validation_status;
                  GRC eval uses static crosswalk + RPV-002 pinned snapshots, not DB rule tables)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — server-side filter + response field; React badge rendering is client work,
                  no new SARO UI surface designed here)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a — SummitCare demo-blocker but no new customer-facing mock)

## Decision Log
Q1 where is the server-side filter applied (AC-1/AC-2)? → inside get_matrix_rows, the single
  aggregation point for list + coverage-counts + CSV export. One filter covers all three customer
  surfaces AND the counts/export edge cases. Filter is SERVER-SIDE (never client-only), fail-closed.

Q2 visibility rules? → default view excludes DRAFT_UNVALIDATED, RETIRED, and NULL (fail-closed,
  treat NULL as draft). Includes SME_VALIDATED always + LEGACY_UNREVIEWED when config flag on.
  Implemented as validation_status IN (allowed) — SQL IN excludes NULL for free.

Q3 which personas get the "show draft content" toggle (AC-3, stop-and-ask)? → ai_auditor + admin
  (resolved from persona_permissions: they hold rule_packs/coverage_gap tabs, trace_mode=technical;
  compliance_lead/risk_officer explicitly deny rule_pack_admin). A show_drafts query param is honored
  ONLY for those personas; requested-but-unprivileged silently forces False (fail-closed, no error).
  Never persisted as a default.

Q4 LEGACY visibility (AC-4)? → config flag saro_show_legacy_rules (default True = visible). Legacy
  rows carry a "PENDING_VALIDATION" badge ONLY in the internal (show_drafts) view — customers never
  see the pending indicator. Product can flip the flag to hide legacy before SummitCare.

Q5 eval-path exclusion (AC-5)? → the GRC audit path is covered by RPV-002 (static crosswalk +
  published-snapshot pin). BUT the legacy 4-gate scoring engine (engine.py) ALSO reads the DB rule
  tables directly to enrich Gate-4 applied rules with obligation text -> that path needed filtering
  too (see DEV-1). engine.py now filters _eu_rules/_gov_rules by the same visibility allow-list.

Q6 RETIRED framework disappears (edge)? → naturally handled: a framework whose rows are all
  RETIRED/filtered produces zero visible rows, so it is absent from the matrix and any selector
  derived from visible rows (e.g. US EO 14110 governance framework — though governance isn't in the
  matrix surface; EU/NIST are the matrix frameworks and neither fully retires).

Q7 companion task? → export the live radar DATA migration radar_scan1_rule_pack_delta_data into the
  repo as migration 031 (the columns migration was already exported as 029 in RPV-001). Idempotent-safe.

## Deviations
- DEV-1 (security-auditor Blocker): I initially scoped AC-5 as "fully covered by RPV-002", but the
  legacy scoring engine (engine.py) loads _eu_rules/_gov_rules with no status filter and
  _lookup_obligations attaches their obligation text to Gate-4 AppliedRuleOut + TRACE — a real
  DRAFT/RETIRED text leak on the scan path. Conservative fix: both loads filter
  validation_status IN rule_visibility.default_visible_statuses() (fail-closed). Pinned by FND-042.
  (The reviewer rated this a narrow text-enrichment leak / nice-to-have; the security-auditor rated it
  a Blocker. Fixed to satisfy the stricter reading — it is a leak-prevention story.)

## Review outcomes (both agents)
- Reviewer VERDICT: APPROVE (no blockers). Nice-to-haves: engine path (fixed, DEV-1/FND-042);
  persona-downgrade log (added logger.info); scope drift (precise per-story staging — stray specs
  NOT committed here).
- Security-auditor VERDICT: FAIL -> Blocker 1 (engine leak) FIXED + pinned (FND-042); Should-fix 2
  (SSO persona self-assignment) is pre-existing -> logged as FND-043 (open, forward work).
