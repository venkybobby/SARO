# Pilot Feedback — Weekly Triage Ritual

**Story:** STORY-382 · **Owner:** Venky · Feeds: STORY-383 (feedback → roadmap)

Pilot learnings have to land in the backlog **by mechanism, not memory**. The
feedback widget (TRACE View, Compliance Hub) captures screen, category, severity,
and a free-text note; this ritual makes sure none of it evaporates.

---

## The ritual (weekly, ~20 min)

1. **List the untriaged:** `saro feedback-triage --status new`.
2. For **every** item, reach exactly one terminal disposition — nothing stays
   `new` after the ritual:
   - **→ a story.** Link a `STORY-###` (or `FND-###`). Set `story_linked` with
     the id. Pilot-originated stories carry a `feedback_ids` reference (STORY-383
     convention) so the loop is traceable both ways.
   - **Declined.** Set `declined` **with a reason** — the system refuses a
     decline without one. A silently-dropped piece of feedback is how a pilot
     stops bothering to give it.
   - **Parked.** Set `parked` for "real, but not now". Parked items are
     re-reviewed the following week, not forgotten.
3. **PHI check.** If any note contains patient information despite the widget's
   notice, treat it as an incident-adjacent data-handling issue: redact the row,
   note it, and (if a customer's data) follow the notification obligations in the
   support model. The feedback table is excluded from evidence exports, but that
   is containment, not permission to ignore a leak.

## Dispositions

| Status | Meaning | Required |
|---|---|---|
| `new` | Not yet triaged | — |
| `triaged` | Reviewed, disposition pending a decision | — |
| `story_linked` | Became (part of) a story | a `story_id` |
| `declined` | Won't do | a reason in the note |
| `parked` | Later | re-reviewed weekly |

## Why free text is allowed here (and nowhere else like it)

A feedback form needs prose — a category and severity cannot capture "the risk
chip is confusing next to the coverage number". So unlike product analytics
(PHI-free by construction), feedback is **mitigated**: a visible no-PHI notice,
a length cap, and exclusion from evidence exports. A pilot's UI gripe must never
appear in an auditor's evidence pack — that exclusion is enforced, not aspired to.

## Cadence & ownership

- **Weekly**, same slot. Skipping a week lets the `new` queue grow past the point
  where it gets triaged honestly.
- One owner runs it (solo-operator model). If delegated later, the disposition
  discipline — every item reaches a terminal state, declines carry reasons —
  travels with it.
