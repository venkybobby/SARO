# STORY-103: Reconcile findings ledger ↔ regression manifest (status drift, not literal dupes)

**Status:** ready (⚠ premise corrected — no duplicate FND IDs exist; real issue is cross-file status drift)
**Screen/Area:** Repo hygiene — quality/findings.md, tests/regression/manifest.yaml

## Goal
The findings ledger (`quality/findings.md`) and the regression manifest (`tests/regression/manifest.yaml`) are two records of the same FND-### items, and they disagree. The ledger must be internally consistent and consistent with the manifest so a finding's status is unambiguous and no finding is tracked in conflicting states. Investigation found **no duplicate FND IDs** (FND-001…FND-013 each appear once); the defect is **status drift** between the two files.

## Context (file:line)
- `quality/findings.md:9-11` — FND-001/002/003 marked `verify-pinned`; lines 17-18 FND-009/010 marked `open`; FND-004–008, 011–013 `pinned`.
- `tests/regression/manifest.yaml` — lists FND-001…013; per investigation FND-001/002 appear as `open` there while `verify-pinned` in findings.md (authoritative-status conflict). Manifest header declares itself append-only and authoritative for test pinning.
- `quality/findings.md:23-24` — defines `verify-pinned` = fix believed shipped but no regression test yet.

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given both files, When every FND-### is cross-checked, Then each ID maps to exactly one status that is consistent across `findings.md` and `manifest.yaml` (a documented mapping: e.g. ledger `verify-pinned` ⇔ manifest `open`/no-test), with the rule for that mapping written into `findings.md`'s legend so it cannot drift again.
- **AC-2:** Given a finding listed in `manifest.yaml`, When it is looked up in `findings.md`, Then it exists there with a matching title and non-contradictory status (no manifest entry orphaned, no ledger entry missing from the manifest).
- **AC-3:** Given the reconciliation, When `pytest tests/regression -q` runs, Then every test referenced by a `pinned` manifest entry exists and passes (no entry points at a missing/renamed test).
- **AC-4:** Given a contributor adds a future finding, When they follow the legend, Then the two files stay in sync by construction (the mapping rule is explicit).

## Edge Cases
- `verify-pinned` entries (FND-001/002/003) that genuinely have no regression test yet — reconciliation must not fabricate a "pinned" claim; reflect reality.
- FND-009/010 are `open` security findings (live follow-ups) — keep `open`, do not silently close.

## Out of Scope
- Actually writing the missing regression tests for `verify-pinned` auth findings (separate work).
- Fixing FND-009/FND-010 themselves.

## Non-Functional Requirements
- The manifest is append-only and authoritative for test pinning — reconcile by aligning `findings.md` to it (or documenting the deliberate ledger-vs-manifest status mapping), never by deleting manifest history.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_status_mapping_is_consistent`, `test_ledger_legend_documents_the_manifest_mapping` | quality/findings.md |
| AC-2 | `test_every_manifest_finding_is_in_the_ledger_and_vice_versa`, `test_no_duplicate_fnd_ids_in_findings_ledger` | quality/findings.md, tests/regression/manifest.yaml |
| AC-3 | `tests/regression/test_manifest_integrity.py` (pinned entries have passing tests) | tests/regression/ |
| AC-4 | legend now documents verify-pinned↔open mapping; guard test fails on future drift | quality/findings.md |

**Status:** done. Confirmed **no duplicate FND IDs** (premise corrected). Real issue was vocabulary drift (`verify-pinned` vs `open`) — documented the cross-file mapping in the legend and pinned ledger↔manifest consistency. Branch `story/STORY-103_findings_ledger_dedupe` (stacked on 104).
