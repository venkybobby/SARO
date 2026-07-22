# Story Quality Conventions

Standards a story spec must meet. Complements
[engineering-standards.md](engineering-standards.md) (which owns the Definition
of Ready/Done and the status-ledger discipline).

---

## Feedback → roadmap traceability (STORY-383)

Pilot learnings must land in the backlog **by mechanism, not memory** — and be
traceable in both directions, so a design partner can be shown "you said → we
shipped" and an engineer can see why a story exists.

### The convention

1. **Every story that originates from pilot feedback carries a `feedback_ids`
   line** in its spec, listing the feedback item id(s) that drove it:

   ```markdown
   **feedback_ids:** 3f2a…, 9c11…
   ```

   The ids are `pilot_feedback.id` values (STORY-382). One story may cite
   several feedback items; one feedback item may be cited by several stories.

2. **Every feedback item carries its disposition** (STORY-382 triage): it
   reaches `story_linked` (with a `story_id`), `declined` (with a reason), or
   `parked`. Nothing stays `new` after the weekly ritual
   ([ops/feedback-triage.md](ops/feedback-triage.md)).

Together these close the loop: `pilot_feedback.story_id` points feedback → story,
and the spec's `feedback_ids` points story → feedback.

### Enforcement

`scripts/check_feedback_traceability.py` verifies the two directions agree:

- a feedback item marked `story_linked` to `STORY-X` **should** appear in
  `STORY-X`'s `feedback_ids` (a one-way link is a broken loop);
- a spec's `feedback_ids` **should** name feedback that exists and is linked back.

> **Note on tooling.** Earlier planning referred to a `saro-story-author` agent
> enforcing this. That agent does not exist in this repository. The convention
> is therefore enforced by the check script above (CI-runnable) and this
> document — not by a phantom agent. (Same correction discipline as the
> validation-strategy numbering: CLAUDE.md FM-2.)

### The quarterly "you said → we shipped" artifact

`scripts/generate_feedback_summary.py` produces a partner-facing summary from the
linkage — never hand-typed, so it cannot drift from what actually shipped. For
each feedback item that became a story, it shows the feedback (redacted to
category/severity/screen, **not** the free-text body — that may be sensitive and
is not for external sharing), the story it drove, and the story's status. This is
the SummitCare renewal artifact.
