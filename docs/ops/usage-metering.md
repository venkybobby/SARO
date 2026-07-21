# Usage Metering & Billing Export

**Story:** STORY-374 (delta on STORY-MTR-001) · **Owner:** Venky

---

## 1. What is metered

Per-tenant, per-period counters, incremented at the evaluate/attest boundary
(`services/audit_submission.py`) and elsewhere. Closed vocabulary — the meter
keys are fixed in `services/metering_service.py`, and dimension tags are a
closed vocabulary of bounded scalars. **There is no free-text field**, so a
meter cannot carry payload or PII (INV-2 by construction, not by redaction).
The export inherits that guarantee: its columns are `tenant_id, period,
meter_key, count` and nothing else.

## 2. The recount invariant — metering is evidence-grade

Metering underlies invoicing, so a meter that is *merely close* to the truth is
a **bug, not a variance**. `saro meter verify` recounts each metered value
against its authoritative table and requires a **0% exact** match:

| Meter | Authoritative table |
|---|---|
| `attestations_issued` | `scan_reports` (one row per attestation) |
| `evaluations_executed` | `audits` |
| `evidence_records_persisted` | `grc_evidence_records` |

Both the meter and the table derive from the same committed rows, so any gap is
a wiring fault, not drift. The boundary increments are idempotent per audit id,
which is what makes the exact recount hold even under a re-submission.

```bash
saro meter verify --tenant <uuid> [--period YYYY-MM]   # exits non-zero on any mismatch
```

> This is distinct from `metering_service.reconcile()`, which alerts on drift
> beyond a *tolerance* as a data-quality signal. Verify is exact; reconcile is
> tolerant. They answer different questions and are kept separate on purpose.

Meters with no single authoritative table (e.g. `adapter_observation_volume`)
are reported as **unverifiable** rather than passed against a fabricated source.

## 3. Export

```bash
saro meter export --tenant <uuid> --period 2026-07 --format csv   # or json
saro meter export --tenant <uuid> --period 2026-07 --out july.csv
```

Rows are sorted by meter key, so a diff of two months' exports is meaningful.

## 4. Scope — export only

**SARO has no payment-processor integration, and none is in scope for this
story.** This is export only: it produces the evidence-grade usage record that a
biller of record draws from. Turning usage into an invoice, applying pricing,
and taking payment happen elsewhere.

A **Stripe** (or equivalent) integration is a deliberate later story, called out
here so the boundary is explicit rather than assumed. Until then, invoicing is a
manual step performed against these exports.
