# STORY-371: Support Model + Incident Response Plan (delta)

**Status:** ready
**Screen/Area:** Ops/compliance docs (Pack Epic 16)
**Ground truth:** `docs/incident-response-plan.md` v1.0 EXISTS (detection →
containment → notification flows); external-sharing gap #1 was already closed by
S-1202 (per GAP_ANALYSIS_2026-06-15). Delta = support model + severity matrix +
tabletop exercise.

## Goal
A pilot customer knows severity definitions, response paths, and who answers at
2am — honest solo-founder model with named backup plan.

## Acceptance Criteria
- AC-1: Support model doc (`docs/ops/support-model.md`): channels, hours, S1–S4
  severity matrix with response/resolution targets consistent with STORY-369
  SLA, escalation path (honest solo-operator model + backup).
- AC-2: IRP updated to v1.1: link severity matrix, add security-incident
  customer-notification timeline commitments, postmortem template appended.
- AC-3: One tabletop exercise run against "leaked credential" hypothetical
  (FND-003 as the scenario); notes committed under docs/ops/tabletop/.
- AC-4: Gap-tracker linkage refreshed (IRP already closed gap #1 — record stays
  accurate, no re-claiming).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_support_model_defines_s1_to_s4_with_targets`, `test_support_model_states_hours_and_solo_operator_model`, `test_support_model_flags_the_missing_backup_responder`, `test_support_model_targets_do_not_exceed_what_the_channel_supports` | `docs/ops/support-model.md` |
| AC-2 | `test_irp_is_v11_and_links_the_support_model`, `test_irp_contains_a_postmortem_template`, `test_postmortem_template_requires_a_systemic_action`, `test_irp_maps_old_p_severities_to_new_s_severities` | `docs/incident-response-plan.md` v1.1 |
| AC-3 | `test_tabletop_notes_are_committed`, `test_tabletop_used_the_real_fnd_003_scenario`, `test_tabletop_found_gaps_and_filed_them`, `test_tabletop_states_nothing_was_executed` | `docs/ops/tabletop/2026-07-21-leaked-credential.md` |
| AC-4 | `test_sla_gate_reflects_the_reconciliation_without_overclaiming`, `test_fnd_064_is_marked_pinned_in_the_ledger` | `docs/legal/sla-draft-v0.1.md` §5, `quality/findings.md` |
| FND-064 | `tests/regression/test_fnd_064_ir_plan_response_commitments.py` (12 tests) | IRP + support model + `routers/governance.py` payload |

## FND-064 reconciled — the commercial decision, made conservatively
The pack left "reduce the times or fund paging" open. Taken: **state what the
current model delivers**, and cost out the alternative rather than silently
assume it. S1 = 1 business hour in hours, best-effort outside; detection ≤60 min
matching the canary. `docs/ops/support-model.md` §6 shows exactly what a paging
tier would change (30 min in hours, 1 hour 24×7) so the owner can price the
upgrade — deliberately not committed, because "the commitment is the expensive
part, and it should not be offered until someone is willing to be woken".

**Key structural fix:** *notification* commitments are now separate from
*response* targets. A 72-hour breach-notification clock is achievable on email;
a 15-minute response clock never was. Conflating them is what produced v1.0's
undeliverable numbers.

The customer-facing `GET /api/v1/governance/ir-plan` payload was updated in the
same change — it served `sla_hours: 1` for a data breach, which read as a 1-hour
response commitment. It now carries 72 with an `sla_basis` naming which clock
each number is.

## Tabletop found three real gaps (not a paper exercise)
Walking FND-003 end to end surfaced, and filed:
- **FND-065** — *nothing emits `AUTH_EVENT`*. No login is recorded anywhere, so
  "was the leaked credential used?" is unanswerable. This also exposed **my own
  FM-2 violation**: in STORY-366 I justified classifying `POST /auth/token` as
  DATA_PLANE with "auth events handled by the auth path" — a mechanism I never
  verified and which does not exist. Justification corrected.
- **FND-066** — password rotation does not invalidate outstanding JWTs (no
  `jti`/`token_version`/denylist), so the secrets-runbook containment step is
  incomplete and gives false confidence.
- **FND-067** — no breach-notification template and no tenant security-contact
  list, despite the 72-hour commitment.

## Human gates still open
- **Named backup responder** (support-model §5) — the largest gap in a solo
  model; blocks external SLA use alongside counsel review.
- FND-065/066/067 fixes — recommended before pilot conversion.
- FND-003 rotation itself (secrets-runbook §4) still open from STORY-363.
