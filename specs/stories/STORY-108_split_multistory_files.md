# STORY-108: Split multi-story spec files into one-file-per-story

**Status:** ready
**Screen/Area:** specs/stories/ (repo hygiene; enforces README "one file per story")

## Goal
Three spec files bundle multiple stories each, violating `specs/stories/README.md` ("One file per story"). Split them into individual `STORY-*.md` files (preserving content verbatim) so `/story <ID>` can target each, and the bundles can be retired.

## Context (file:line)
- `specs/stories/SARO_RiskForm_Stories.md` — 4 stories: STORY-RISKFORM-001/002/003/004 (`#` headers + `---`).
- `specs/stories/SARO_AIInsights_Stories.md` — 6 stories: STORY-001…006 (all `done`) (`#` headers + `---`).
- `specs/stories/SARO_Stories_Reports_Settings_Nav_Mobile.md` — 26 stories under 4 `##` sections: REP-001…005, SET-001…005, NAV-001…006, MOB-001…005 (`###` headers + `---`).
- Single-story reference format: `specs/stories/STORY-CI-001.md`; template `specs/stories/_TEMPLATE.md`.

## Decision Required (resolve at Definition-of-Ready)
File-naming for split-out files. **Default:** keep each story's existing ID as filename — `STORY-RISKFORM-001.md`, `REP-001.md` … OR prefix the generic AIInsights `STORY-001…006` (which collide with no current file but are ambiguously generic) as `STORY-AIINSIGHTS-001.md`. Confirm the AIInsights renaming; the rest map 1:1 from their IDs.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given each multi-story bundle, When split, Then every contained story becomes its own `specs/stories/<ID>.md` whose body is the original story block verbatim (Status/Screen/Goal/ACs/etc. preserved), conforming to `_TEMPLATE.md` section order.
- **AC-2:** Given the 36 stories total (4+6+26), When the split completes, Then 36 individual files exist and a count check confirms no story block was dropped or duplicated.
- **AC-3:** Given the original bundle files, When the split is verified complete, Then each bundle is either deleted or reduced to a stub index that links to the split files (default: delete; keep the end-of-file summary tables only if relocated to a README section) — chosen consistently and noted.
- **AC-4:** Given any cross-reference to a bundle filename elsewhere in the repo, When grepped, Then references are updated to the new per-story files (or none exist).

## Edge Cases
- Section summary tables at the end of the Reports/Settings/Nav/Mobile bundle (dependency map) — relocate to a README rather than lose them.
- Stories marked `done` (AIInsights) — preserve their `done` status and traceability tables exactly.
- ID collision: ensure no new filename clashes with an existing `specs/stories/*.md`.

## Out of Scope
- Editing the content/ACs of any split story.
- Re-running any of those done/legacy stories.

## Non-Functional Requirements
- Pure content move; no behavior change. Verify byte-equivalence of each story block pre/post split.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1/AC-2 | `test_all_31_split_stories_exist`, `test_each_split_file_is_a_single_wellformed_story` | specs/stories/STORY-{RISKFORM,AIINSIGHTS,REP,SET,NAV,MOB}-*.md |
| AC-3 | `test_bundles_are_removed`; summaries relocated to README.md | specs/stories/README.md |
| AC-4 | no repo refs to the bundle filenames remained | — |

**Status:** done. Split into **31** files (corrected count: the big bundle held 21 stories, not 26 — RiskForm 4 + AIInsights 6 + REP 5 + SET 5 + NAV 6 + MOB 5). AIInsights generic `STORY-00N` remapped to `STORY-AIINSIGHTS-00N` (default). Bundle summary/dependency tables relocated to `specs/stories/README.md`. Branch `story/STORY-108_split_multistory_files` (stacked on 103).
