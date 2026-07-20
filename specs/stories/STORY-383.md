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
