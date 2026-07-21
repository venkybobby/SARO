# STORY-374: Usage Metering + Billing Export

**Status:** ready
**Screen/Area:** Backend (Pack Epic 17)

## Goal
Per-tenant metering of billable events (evaluations, records ingested,
attestations issued) — evidence-grade (recountable from authoritative tables),
exportable monthly. No payment processing.

## Acceptance Criteria
- AC-1: Metering events captured at the evaluate/attest boundary, keyed by
  tenant, aggregated daily (`usage_meter_daily` table + service).
- AC-2: Recount invariant: recomputing counts from the authoritative records
  (scan/trace/attestation tables) matches the meter exactly (0% drift) —
  regression test + `cli.py meter-verify` command.
- AC-3: Monthly CSV/JSON export per tenant (`cli.py meter-export`).
- AC-4: Doc states explicitly: export only, Stripe/payments is a later story.
- AC-5: Zero PHI/payload content in metering records (INV-2 — counts + ids only).

## DELTA on STORY-MTR-001 (not a rebuild)
MTR-001 already delivered PHI-free meters (closed vocabulary + 64-char value
cap), idempotency, immutable statements, and tolerance-based `reconcile()`. This
story adds only the three things the pack asks for that were missing.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_attest_boundary_increments_are_idempotent_per_audit` | `services/audit_submission.py` (meters `evaluations_executed` + `attestations_issued` at the boundary, deduped by audit id) |
| AC-2 | `test_meter_matching_the_table_verifies_exactly`, `test_undercount_fails_the_exact_check`, `test_overcount_fails_the_exact_check`, `test_verify_exact_is_period_scoped` | `metering_service.verify_exact`, `cli.py meter verify` |
| AC-3 | `test_csv_export_has_a_header_and_one_row_per_meter`, `test_json_export_round_trips`, `test_export_is_stable_ordered_for_diffable_months` | `metering_service.export_csv/export_json`, `cli.py meter export` |
| AC-4 | `test_doc_states_export_only_no_payment_processor` | `docs/ops/usage-metering.md` §4 |
| AC-5 | `test_export_columns_are_a_closed_set_with_no_free_text` (inherited from MTR-001's closed vocabulary) | export columns fixed to `tenant_id,period,meter_key,count` |

## Design notes
- **Exact recount, not tolerance.** `verify_exact` requires 0% difference
  against the authoritative table because metering underlies invoicing — a meter
  that is merely close is a wiring bug, not a variance. Kept separate from
  MTR-001's `reconcile()` (drift-tolerant data-quality alerting); they answer
  different questions and overloading one would blur both.
- **Boundary increments are idempotent per audit id**, which is what makes the
  exact recount hold under a re-submission. One ScanReport = one attestation.
- **Meters with no single authoritative table** (adapter volume) report as
  `unverifiable`, never passed against a fabricated authority.
- **Export inherits PHI-freeness** — fixed columns, no dimension/free-text field.
- **Export only.** No payment processor; Stripe named as a later story so the
  boundary is explicit, not assumed.
