---
name: saro-lifecycle
description: Use for ANY implementation work in the SARO repo — stories, findings, features, refactors, ports, UI work. Drives every task through the DISCOVER→SHAPE→PREVIEW→PLAN→BUILD→VERIFY→SELL lifecycle so the human never has to invoke the individual workflow prompts. Also use when the user says "start", "build", "implement", "fix", or references a STORY-* id.
---

# SARO Lifecycle

Every non-trivial task moves through these stages IN ORDER. You decide which
stages apply using the auto-trigger rules; you do not wait to be asked. Record
progress in the `## Lifecycle` checklist of `implementation-notes.md` — hooks
read that file to enforce gates, so keep it truthful.

## Task classification (do this first, silently)

- **trivial** — single-file, no interface/data-model change, no user-facing
  change. Write `Stage: trivial` at the top of implementation-notes.md and
  skip straight to BUILD. All gates stand down.
- **standard** — everything else. Full lifecycle, stages skipped only per
  their skip conditions below.

## Stage 0 — DISCOVER (blindspot pass)

**Trigger:** the task touches a subsystem or domain with no prior entry in
implementation-notes.md history, no ADR coverage, or the user's phrasing
signals unfamiliarity ("I don't know", "never touched", vague nouns).
**Skip:** area is well-trodden (existing stories, ADRs, or recent notes cover it).

Do: map the territory (code exploration or domain mental model), list the
unknown unknowns — concepts, invariants, gotchas where the user's ignorance
would produce a bad instruction — and for each, the question they *should* be
asking. Finish with the user's request rewritten as an expert would phrase it,
constraints explicit. Get their reaction before advancing.

## Stage 1 — SHAPE

**1a. Brainstorm — trigger:** the request is a rough problem, not a specified
change ("users churn after onboarding", "compliance hub feels slow").
**Skip:** the change is already specified (a STORY-* with acceptance criteria).

Do: search the codebase first, then exactly 10 interventions ordered cheapest
→ most ambitious, each with name / where (files) / what / cost / 2-week
signal. Implement nothing. Ask which resonate.

**1b. Interview — trigger:** always, for standard tasks, after scope is picked.
**Skip:** only if a decision log already exists for this story.

Do: one question at a time, wait for each answer. Prioritize questions whose
answers change architecture (data model, boundaries, sync/async, tenancy,
retention). Never ask what the codebase, CLAUDE.md, ADRs, or SARO's locked
invariants already answer. Offer 2–3 options + your recommended default per
question. Stop when remaining ambiguity is cosmetic. Output a **Decision Log**
(question → answer → architectural consequence) into implementation-notes.md.
The gate hook blocks source edits on standard tasks until this section exists.

## Stage 2 — PREVIEW

**Trigger:** any user-facing surface changes (Dashboard, Compliance Hub,
TRACE View, new UI).
**Skip:** backend-only work.

Do: a single self-contained HTML file, fake data only, zero imports from the
real app. If the design direction is undecided, produce FOUR genuinely
divergent directions in one page (labeled, with the design bet each makes,
sticky nav). If direction is settled, one mock of the specific surface with
cheap clickable interactions. Save at repo root as mock-<name>.html or
design-directions.html. STOP for reaction; list 3–5 questions the reaction
should answer. Never wire a mock into the real app before reaction.

## Stage 3 — PLAN

**Trigger:** always for standard tasks. **Skip:** never.

**3a. Premise check — MANDATORY, runs first.** Any plan that references a prior
artifact (story ID, corpus, rule-pack, document, endpoint, migration) must
verify each reference against the repo before planning on top of it:

- Grep for it; cite the **file path** that proves it exists.
- Anything unverifiable is marked `PREMISE-UNVERIFIED` in the plan — never
  assumed, never softened to "presumably exists".
- A false load-bearing premise is surfaced to the user *before* dependent work
  is written.

This exists because 26 stories were once authored on top of an epic
(STORY-340..357) and two rule-packs that had been planned, described as
delivered in conversation, and never built. See CLAUDE.md FM-1/FM-2.

Record the check as a small table in implementation-notes.md:
`| referenced artifact | verified? | file path or PREMISE-UNVERIFIED |`

**3b. The plan.** Implementation plan ordered by tweak-likelihood — (1) data
model changes, (2) new type interfaces, (3) user-facing behavior, then
everything mechanical buried at the bottom with a one-line "trusted
refactoring" summary. Plan must cite the Decision Log entries it satisfies.
Confirm before BUILD.

**Vocabulary discipline (all stages).** In notes, specs, commits, and session
summaries: *drafted / specified* describes a document; *implemented / merged*
describes code that exists in git. Never "done" or "complete" — those are the
words that let a written backlog be remembered as shipped software.

## Stage 4 — BUILD

**Trigger:** plan confirmed (or task is trivial).

Rules while building:
- Maintain implementation-notes.md continuously. On any forced deviation from
  plan: pick the conservative option, log under `## Deviations` (what / why /
  what the aggressive option was), keep going. Stop only for irreversible
  actions or locked-invariant conflicts.
- **Port sub-protocol** — if the task references an existing implementation
  to replicate (any "like X does it" / vendor reference): read the source
  fully, extract semantics (state machine, invariants, edge cases, error and
  timing behavior), write a 10–20 line semantics spec, show it, then
  reimplement idiomatically in the target — never transliterate. Pin the
  semantics with tests. Log anything that doesn't carry over.
- All existing SARO plugin rules (regression manifest, quality ratchet,
  pre-edit standards) still apply — this lifecycle wraps them, it does not
  replace them.

## Stage 5 — VERIFY (debrief)

**Trigger:** change spans 3+ files, touches a locked invariant, or user asks.
**Skip:** trivial tasks.

Do: build change-debrief.html — a single self-contained report: context (why
this exists, plain language), intuition (mental model + inline-SVG before/
after flow diagram), file-by-file what-was-done with every logged deviation
flagged, what was deliberately NOT done, risk map (each risk → covering test
or gap), and a 6–10 question interactive quiz at the bottom (why-questions and
what-breaks-if questions, reveal-on-click, self-score). The quiz tests
understanding, not filename recall. Offer this before commit; the Stop hook
reminds if skipped.

## Stage 6 — SELL (package)

**Trigger:** only on request, or when the story is design-partner-facing
(SummitCare deliverables). Never automatic otherwise.

Do: one document (buy-in.md) — demo GIF/screenshot FIRST (generate from the
prototype or leave a marked capture-instructions placeholder), then: what
this is (3 sentences, no jargon) / why now / the specific ask / short
technical summary / known deviations & open questions from
implementation-notes.md / links. Plus a <150-word paste-ready Slack message.

## implementation-notes.md template (create at task start)

```markdown
# <STORY-ID or task name>
Stage: standard | trivial

## Lifecycle
- [ ] discover   (or: skipped — reason)
- [ ] shape
- [ ] preview    (or: skipped — backend-only)
- [ ] plan
- [ ] build
- [ ] verify
- [ ] sell       (or: n/a)

## Decision Log

## Deviations
None yet.
```

Check items off as stages complete. Hooks parse this file; never check off a
stage that didn't happen.

**Recreate it at the start of every task.** The gate treats a committed,
unmodified implementation-notes.md as a *finished* task's leftover and blocks
source edits until you rewrite it for the current task — so a stale notes file
can never satisfy the gate for unrelated work. Overwriting the file (new Stage
line + fresh Decision Log) is what clears the gate.
