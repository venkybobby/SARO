# STORY-383: Feedback → Roadmap Traceability

**Status:** ready
**Screen/Area:** Docs + script (Pack Epic 19)
**Depends on:** STORY-382

## Goal
SummitCare learnings land in the backlog by mechanism: every feedback-originated
story is linked, every feedback item has a disposition, and a "you said → we
shipped" summary is generatable.

## Acceptance Criteria
- AC-1: Convention documented: stories originating from pilot feedback carry a
  `feedback_ids:` line in their spec; every feedback item carries disposition
  (STORY-382 status field + linked story id column).
- AC-2: Quarterly summary generator (`scripts/generate_feedback_summary.py`)
  produces "you said → we shipped" from the linkage.
- AC-3: Convention added to docs/engineering-standards.md (story-quality
  section) so story review enforces it.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_a_fully_linked_loop_is_consistent`, `test_story_linked_feedback_without_a_back_reference_is_flagged`, `test_spec_citing_nonexistent_feedback_is_flagged` | `scripts/check_feedback_traceability.py` (bidirectional), wired into `quality-gates.yml` |
| AC-2 | `test_summary_lists_only_story_linked_feedback`, `test_summary_omits_the_free_text_body`, `test_summary_is_generated_not_hand_written` | `scripts/generate_feedback_summary.py` → `docs/feedback-you-said-we-shipped.md` |
| AC-3 | `test_story_quality_doc_defines_the_feedback_ids_convention`, `test_convention_is_referenced_from_engineering_standards`, `test_doc_is_honest_that_saro_story_author_does_not_exist` | `docs/story-quality.md`, `docs/engineering-standards.md` |

## Design notes
- **Loop closed both ways:** feedback → story via `PilotFeedback.story_id`
  (STORY-382); story → feedback via a spec `feedback_ids:` line. The checker
  flags a one-way link in either direction — a story_linked feedback whose spec
  omits the back-reference, and a spec citing feedback that does not exist.
- **The "you said → we shipped" summary is generated**, never hand-written, and
  deliberately **omits the free-text body** (may be sensitive; the partner
  artifact shows category/severity/screen + the story only).
- **Honest about the missing agent:** the pack's AC-3 said "so saro-story-author
  enforces it" — that agent does not exist in this repo. The convention is
  enforced by a CI-runnable check script + the docs, not a phantom agent (same
  FM-2 correction discipline as the validation-strategy numbering).
