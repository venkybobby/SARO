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

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
