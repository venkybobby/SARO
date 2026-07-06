# SARO — Agent Instructions (Codex CLI)

> Canonical repo: https://github.com/venkybobby/SARO (remote `origin`). This
> file is read by Codex every session. It mirrors the Claude Code
> `saro-lifecycle` skill so both tools drive work through the same lifecycle.
> The SARO positioning non-negotiables and commit/testing conventions in
> `CLAUDE.md` apply here unchanged.

## SARO Lifecycle — applies to ALL implementation work

Classify every task first:
- **trivial** — single file, no interface/data-model/user-facing change.
  Write `Stage: trivial` atop implementation-notes.md; skip to BUILD.
- **standard** — everything else; walk the stages below IN ORDER. Announce
  each transition in one line, then execute. Ask before skipping a stage
  whose trigger fired; never ask permission to run one.

Create implementation-notes.md at task start:

    # <task/story id>
    Stage: standard | trivial
    ## Lifecycle
    - [ ] discover  - [ ] shape  - [ ] preview  - [ ] plan
    - [ ] build     - [ ] verify - [ ] sell (n/a unless asked)
    ## Decision Log
    ## Deviations
    None yet.

**0 DISCOVER** — trigger: unfamiliar subsystem/domain or user signals
unfamiliarity. Map the territory, list unknown unknowns (concepts, invariants,
gotchas where ignorance produces bad instructions) with the question the user
should be asking for each, and end with their request rewritten as an expert
would phrase it. Get a reaction before advancing.

**1a BRAINSTORM** — trigger: rough problem, not a specified change. Search the
codebase, then exactly 10 interventions cheapest → most ambitious (name /
files / what / cost / 2-week signal). Implement nothing; ask which resonate.

**1b INTERVIEW** — trigger: always on standard tasks. One question at a time,
architecture-changing questions first (data model, boundaries, sync/async,
tenancy, retention); never ask what the codebase, AGENTS.md, ADRs, or SARO's
locked invariants already answer; offer options + a recommended default. Write
the Decision Log (Q → A → consequence) into implementation-notes.md. **No
source file is edited on a standard task before the Decision Log exists.**

**2 PREVIEW** — trigger: any user-facing change. Single self-contained HTML,
fake data, zero real-app imports. Direction undecided → four genuinely
divergent labeled directions in one page; decided → one clickable mock. Stop
for reaction with 3–5 questions the reaction should answer. Never wire a mock
in before reaction.

**3 PLAN** — always. Order by tweak-likelihood: data model → type interfaces →
user-facing → (bottom, summarized) mechanical refactoring. Cite Decision Log
entries. Confirm before building.

**4 BUILD** — keep implementation-notes.md current. Deviations: conservative
option, log under ## Deviations (what/why/aggressive alternative), keep going;
stop only for irreversible actions or locked-invariant conflicts. If the task
references an implementation to replicate: extract semantics into a 10–20 line
spec, show it, reimplement idiomatically (never transliterate), pin with
tests, log what doesn't carry over.

**5 VERIFY** — trigger: 3+ files or locked invariant touched. Produce
change-debrief.html: context, intuition (inline-SVG before/after flow),
file-by-file walkthrough with deviations flagged, deliberately-not-done, risk
map (risk → covering test or gap), and a 6–10 question reveal-on-click quiz
(why / what-breaks-if) that tests understanding, not filename recall. Check
off `verify` only after producing it (or mark skipped with a reason).

**6 SELL** — only on request or design-partner-facing work. One buy-in.md:
demo GIF first, what/why-now/the-ask, short technical summary, deviations &
open questions, links; plus a <150-word Slack paste.

Self-check before declaring any multi-file task done: implementation-notes.md
updated this session, lifecycle boxes truthful, Deviations section present.
Treat a violation as an unfinished task. CI enforces the same.
