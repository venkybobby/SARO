# Sample-Level Evidence — Retention & Redaction Policy

> **Status:** v1.0 · Owner: Jordan Lee (Backend) · 2026-06-12 · PT-002 / STORY-005

## What is persisted

For every Gate-3 detection SARO persists a `SampleFinding` row: `audit_id`, `sample_id`,
`domain`, `matched_signal`, a **redacted** `matched_text_fragment`, and `weight`. This lets an
auditor drill from a domain-level finding down to the exact samples and fragments that triggered it
(`GET /api/v1/traces/{audit_id}/samples`).

## No raw PII at rest

Fragments are redacted by `engine._redact_pii()` **before** the database write — SSN, credit-card,
email, phone, and passport patterns are masked. A fragment that is entirely PII is stored as the
mask, never the raw value. Redaction is pinned by tests in `tests/test_v3_gaps.py` and
`tests/test_pt002_*`.

## Signal-level de-duplication

Findings are de-duplicated at persistence to one row per
`(sample_id, domain, matched_signal)` (`routers/scan._dedupe_findings`). Domain-level counts are
preserved in the `AuditTrace.detail_json` (`sample_count`, `top_sample_ids`), so de-duplication
never loses the aggregate count.

## Retention window

| Tier | Retention | Basis |
|---|---|---|
| Sample findings (`sample_findings`) | Tied to the parent audit's retention; default **365 days** | Operational/audit-evidence window; configurable per tenant contract |
| Audit trace chain (`audit_traces`) | Lifetime of the audit record (append-only) | Tamper-evident evidence integrity |

`SampleFinding` rows cascade-delete with their parent `Audit` (`ondelete="CASCADE"`), so deleting an
audit at the end of its retention window removes its sample-level evidence atomically. There is no
silent background purge; deletion is an explicit, logged operation. Historical findings remain
queryable for the full retention window via the samples endpoints.

## Product analytics (STORY-381) — disclosed collection

SARO collects **first-party, PHI-free product-analytics events** (`product_events`)
to inform roadmap decisions: coarse usage signals such as logins, attestation
views, rule-pack subscriptions, first evaluations, and Compliance Hub artifact
views.

- **No personal data by construction.** Each event carries a closed-vocabulary
  name, a tenant id, a timestamp, and closed-vocabulary property tags of bounded
  scalars. There is no free-text field, no user id or email, and no payload or
  patient content — see `docs/analytics/event-schema.md`. Because events contain
  no personal data, they are not "personal data" under the DPA; the collection is
  disclosed here regardless.
- **First-party only.** Events are stored in SARO's own database. No third-party
  analytics processor receives this data; adopting one would be a disclosed
  sub-processor change subject to security review.
- **Retention:** product-analytics events are retained for **395 days** (13
  months, for year-over-year trend), then purged. They are not evidence records
  and are excluded from evidence exports.

## Out of scope

- Backfilling sample-level evidence for audits run before this feature shipped.
- Storing full (un-redacted) sample text — only redacted fragments are ever persisted.
