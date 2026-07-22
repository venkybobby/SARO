# STORY-380: Epic 13 Closure Audit (ground-truth corrected)

**Status:** ready
**Screen/Area:** Docs (Pack Epic 18)
**Ground truth:** The pack's "Epic 13 = STORY-340..357" never existed in this
repo. The honest closure audit covers what DOES exist as validation machinery:
STORY-335..338 plus the offline qa_lab, and records the correction.

## Goal
No zombie stories: a one-page audit of the actual validation-machinery state,
each item Done (evidence link) / Superseded by Pack-Epic-18 story / Deliberately
dropped (reason).

## Acceptance Criteria
- AC-1: `docs/validation/epic13-closure-audit.md` triages STORY-335..338 and any
  other validation-adjacent work with evidence links.
- AC-2: Records the numbering correction (no STORY-340..357 ever existed) so
  future packs don't re-assume it.
- AC-3: Marks the (corrected) epic closed with a one-page summary; open items
  point at STORY-377/378/379.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_audit_triages_335_to_338_with_evidence`, `test_audit_links_evidence_that_exists_in_the_repo`, `test_epic13_stories_genuinely_do_not_exist` | `docs/validation/epic13-closure-audit.md` |
| AC-2 | `test_audit_records_that_epic13_never_existed`, `test_audit_records_the_strategy_version_correction` | same |
| AC-3 | `test_audit_names_the_human_gate_rather_than_claiming_completeness`, `test_audit_discloses_only_t1_is_measured`, `test_audit_has_a_verdict` | same |

## The correction this story records
The pack assumed "Epic 13 = STORY-340..357". Those never existed. So the audit
triages the validation machinery that DOES exist (STORY-335..338 + Pack-Epic-18
377..380), each with a git-verifiable evidence pointer, and records that Epic 13
was a planning artifact carried forward as fact — the FM-1/FM-2 pattern. A test
(`test_epic13_stories_genuinely_do_not_exist`) fails if those phantom stories
ever appear, so the audit's premise cannot silently rot.

Closed honestly: the verdict names the STORY-377 human gate and the T1-only
coverage rather than claiming a completeness the validation track has not
reached.
