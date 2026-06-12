# STORY-108: Split Multi-Story Files for Branch-per-Story Traceability (G-8, carry-over)
Status: ready
Screen/Area: Quality Infrastructure / `SARO_RiskForm_Stories.md` (4 stories), `SARO_AIInsights_Stories.md` (6 stories)

## Goal
Two files violate the one-story-per-file rule that branch-per-story traceability depends on: a branch, PR, and test manifest entry must map 1:1 to a story file. Split the 10 embedded stories into individual files following the standard template, and add an enforcement check so the violation cannot recur.

GRC mapping: ISO/IEC 42001 A.6.2 (AI system life cycle documentation); EVF traceability chain (story → branch → tests → evidence).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given `SARO_RiskForm_Stories.md`, When split, Then 4 individual story files exist, each with a unique STORY/S-XXX ID, full template sections, and content faithfully migrated (no silent rewording of acceptance criteria).
- AC-2: Given `SARO_AIInsights_Stories.md`, When split, Then 6 individual story files exist under the same conditions.
- AC-3: Given the split completes, When the original combined files are checked, Then they are deleted (after confirmation) or reduced to index stubs linking the new files — one or the other, decided by the product owner, not both styles.
- AC-4: Given CI or the `/story` command, When a story file containing more than one `STORY-` / `S-` header is committed, Then the quality gate fails naming the file.
- AC-5: Given the regression test manifest and findings ledger, When story IDs are cross-referenced, Then all references resolve to the new per-story files.

## Edge Cases
- Stories inside the combined files lacking required template sections → mark `Status: draft` and list missing sections; do not invent acceptance criteria.
- In-flight branches named after the combined files → enumerate and rename mapping in the PR description.

## Out of Scope
- Implementing the RiskForm/AIInsights stories themselves.

## Non-Functional Requirements
- Standard project rules; deletion of originals requires confirmation.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
