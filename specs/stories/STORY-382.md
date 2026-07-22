# STORY-382: Structured Pilot Feedback Intake

**Status:** ready
**Screen/Area:** Backend now; TRACE View / Compliance Hub widget deferred to
screen review (Pack Epic 19, D7)

## Goal
Pilot feedback arrives categorized with context (screen, tenant, category,
severity) instead of ad-hoc email.

## Acceptance Criteria
- AC-1: `POST /api/v1/feedback` capturing screen, tenant (from auth), category
  (bug/gap/confusing/feature), severity, free text; server-side length limit.
- AC-2: API/schema carries the "do not include patient information" notice
  (docstring + response contract for the widget to display); feedback table
  excluded from evidence exports (INV-2 hygiene — regression test).
- AC-3: `feedback` Supabase table with triage status field
  (new/triaged/story-linked/declined/parked); RLS tenant-scoped writes,
  operator-read-all; internal triage view = privileged GET + CLI listing.
- AC-4: Weekly triage ritual documented (`docs/ops/feedback-triage.md`): every
  item → story ID, declined (with reason), or parked.
- AC-5: Frontend widget deferred pending saro-screen-review; API contract ready.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_feedback_captures_the_required_fields`, `test_unknown_category_is_rejected`, `test_routes_are_registered_and_authenticated` | `models.PilotFeedback`, migration 041, `services/feedback_service.py`, `routers/feedback.py` |
| AC-2 | `test_body_over_the_length_cap_is_rejected`, `test_no_phi_notice_is_part_of_the_form_contract`, `test_feedback_table_is_excluded_from_evidence_exports` | length cap + `NO_PHI_NOTICE` in the form contract + export-exclusion guard |
| AC-3 | `test_triage_links_a_story`, `test_declined_requires_a_reason`, `test_triage_view_lists_and_filters` | triage lifecycle; `GET /feedback/triage` (operator), `cli.py feedback-triage` |
| AC-4 | `test_ritual_doc_requires_every_item_to_reach_a_disposition`, `test_ritual_doc_states_the_export_exclusion` | `docs/ops/feedback-triage.md` |

## Design note — free text handled honestly
Unlike analytics/metering (PHI-free by construction), a feedback form NEEDS free
text. So INV-2 is **mitigated, not eliminated**, and the mitigations are the
whole design: a visible "do not include patient information" notice served in
the form contract (so the widget shows it), a server-side length cap, and the
feedback table **excluded from evidence exports** — a pilot's confusing-UI note
must never surface in an auditor's evidence pack. The export exclusion is a
structural guard test, not an aspiration.

Feedback is **attributable** (user_id) — the opposite of analytics — because it
is a support channel and following up needs to know who reported.

## Human gate
Frontend widget deferred to saro-screen-review (D7); the API contract
(`GET /feedback/form`) is ready so the widget renders from it. `pilot_feedback`
carries RLS (migration 041) and is in the tenant-isolation census.
