# STORY-381: Privacy-Safe Product Analytics

**Status:** ready
**Screen/Area:** Backend + docs (Pack Epic 19)

## Goal
Roadmap decisions use behavior data: first-party, PHI-free usage analytics on
SARO's own UI/API.

## Acceptance Criteria
- AC-1: Event schema doc FIRST (`docs/analytics/event-schema.md`): event name,
  properties, tenant id — no PHI, no payload content, no free-text capture
  (INV-2 by construction; schema validator enforces property allowlist).
- AC-2: First-party capture: `product_events` table in Supabase (self-hosted
  option; third-party SaaS explicitly NOT chosen without sign-off — Epic 15
  security-review question).
- AC-3: Key funnels instrumented server-side: login → view attestation,
  rule-pack subscribe → first evaluation, Compliance Hub artifact views.
- AC-4: Internal query set for the founder (`docs/analytics/queries.md` +
  `cli.py analytics-summary`).
- AC-5: Analytics disclosed in the DPA/data-retention doc (ties to gating gap #3
  artifacts: docs/sample-evidence-retention.md, DPA template).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_event_carries_no_free_text_column`, `test_unknown_property_key_is_rejected`, `test_oversized_property_value_is_rejected`, `test_closed_value_allowlist_is_enforced` | `docs/analytics/event-schema.md` (written first), `services/product_analytics.py`, `models.ProductEvent` |
| AC-2 | `test_analytics_is_disclosed_in_the_retention_doc`, `test_schema_doc_names_third_party_saas_as_signoff_gated` | migration 040 (`product_events` in Supabase); first-party only |
| AC-3 | `test_login_handler_emits_a_login_event`, `test_subscribe_emits_a_subscribe_event`, `test_first_evaluation_is_emitted_once_per_tenant` | `routers/auth.py`, `services/rule_pack_lifecycle.py`, `services/audit_submission.py` |
| AC-4 | `test_analytics_summary_command_exists`, `test_queries_doc_covers_the_key_funnels` | `cli.py analytics-summary`, `docs/analytics/queries.md` |
| AC-5 | `test_analytics_is_disclosed_in_the_retention_doc`, `test_retention_doc_states_a_retention_period_for_analytics` | `docs/sample-evidence-retention.md` |

## Design notes
- **PHI-free by construction** (metering precedent): closed event vocabulary +
  closed property-key allowlist + bounded scalar values + **no free-text
  column**. A caller cannot smuggle content in — pinned by tests feeding a
  free-text property, an oversized value, a non-scalar, and an off-allowlist
  value, all rejected.
- **No individual user identity in an event** — tenant id is the only
  identifier. Actor tracking is the audit trail's job (STORY-366/FND-065), a
  different system behind authorization.
- **Fail-open** — analytics never breaks or unwinds a request; a lost event is
  acceptable, a 500 on login is not.
- **First-party only** — a third-party analytics SaaS is a sub-processor /
  security-review question and is NOT adopted without sign-off (stated in doc).
- New `product_events` table carries RLS (migration 040) and is registered in
  the tenant-isolation census — the census guard would have caught its omission.
