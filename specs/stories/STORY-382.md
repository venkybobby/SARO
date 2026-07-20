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
