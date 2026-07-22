# STORY-377: Define the Oracle Completion Bar (FP/FN targets)

**Status:** ready (sign-off human-gated)
**Screen/Area:** Validation docs (Pack Epic 18)
**Ground truth:** No "validation strategy v1.1" or 4-tier labeled corpus exists
(pack assumption corrected — see STORY-PACK-14-19-INDEX). This story CREATES
validation strategy v1.0 with tiers, proposed thresholds, and protocol.

## Goal
"Validated" becomes a number with a method: per-pack FP/FN targets + measurement
protocol, proposed with tradeoffs for explicit human sign-off.

## Acceptance Criteria
- AC-1: For RP-OBS-COMPLETE and RP-TOOL-SCOPE: proposed precision/recall
  thresholds with rationale, per ground-truth tier. Tiers defined in this doc
  (T1 synthetic-deterministic, T2 synthetic-adversarial, T3 offline
  qa_lab-labeled (STORY-338 harness), T4 pilot-labeled — future).
- AC-2: Measurement protocol: corpus composition, tier weighting, exclusion
  rules, re-measurement cadence, re-validation triggers (pack version bump,
  adapter addition).
- AC-3 **[HUMAN — OPEN]**: threshold sign-off. Numbers are PROPOSED in the doc
  with tradeoffs; the bar is not active until signed. Do not self-certify.
- AC-4: Documented as `docs/validation/validation-strategy-v1.0.md`.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_two_profiles_are_offered_not_one_preset_choice`, `test_thresholds_cover_both_packs_across_available_tiers`, `test_t4_pilot_thresholds_are_blank_because_no_data_exists` | `docs/validation/validation-strategy-v1.0.md` §4, `quality/validation/completion-bar.proposed.yaml` |
| AC-2 | `test_protocol_is_per_tier_not_a_blended_average`, `test_protocol_states_exclusions_cadence_and_triggers` | strategy §5 |
| AC-3 | `test_proposed_bar_is_not_in_force`, `test_proposal_file_is_not_marked_signed`, `test_strategy_doc_carries_a_human_signoff_gate` | `services/validation_bar.py` (unsigned ⇒ no thresholds), strategy §6 |
| AC-4 | `test_strategy_records_the_numbering_correction` | strategy v1.0 (not v1.2 — v1.1 never existed) |

## The gated part — and how it is enforced structurally
AC-3 forbids self-certifying the bar. So:
- **Two profiles are proposed** (recall-weighted vs balanced), not one — the
  FP/FN tradeoff (§3) is presented for the owner to decide, not decided by me.
- `services/validation_bar.py` returns **`None` thresholds unless a bar is
  SIGNED**. `test_proposed_bar_is_not_in_force` asserts it is not. So STORY-378's
  harness and STORY-376's validation stage physically cannot enforce a bar SARO
  set for itself — there is no code path to an unsigned enforcement.
- T4 (pilot) thresholds are left blank in both profiles: proposing a number for
  data that does not exist is the fabrication this whole story guards against.

## Human gate — [HUMAN — OPEN], blocks STORY-378/379 + STORY-376 FP/FN
Owner action (strategy §6): choose Profile A or B (or amend), accept/amend the
FP/FN tradeoff, sign, then set `status: SIGNED` + `chosen_profile` in the YAML
and rename it to `completion-bar.yaml`. Until then the bar is inert by
construction.
