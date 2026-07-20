# STORY-376: Customer Rule-Pack Authoring & Update Workflow (delta)

**Status:** ready
**Screen/Area:** Backend (Pack Epic 17)
**Ground truth:** RPV-001/002 already deliver immutable, hash-chained published
snapshots + publish API (`routers/rule_pack_versions.py`,
`services/rule_pack_snapshot_service.py`). Delta = draft/validation states ahead
of publish + tenant version pinning + audit-log wiring.

## Goal
draft → validate → publish lifecycle for rule-packs so a customer compliance
lead can author packs without SARO engineering — published versions stay
immutable (INV-7).

## Acceptance Criteria
- AC-1: Lifecycle states on working-copy packs: `draft` (editable) →
  `validation` (runs pack against tenant's synthetic/labeled corpus; reports
  FP/FN vs the STORY-377 bar) → `published` (existing immutable snapshot path).
- AC-2: Regression test: publishing a new version does not alter attestations
  produced under prior versions; attestations record exact pack version+hash
  (extends existing provenance tests).
- AC-3: Tenant version pinning (subscription pins a published version); no
  deletes of published packs — deprecation = pin elsewhere.
- AC-4: All lifecycle transitions write to the STORY-366 admin audit log.
- AC-5: Authoring guide doc for customers (`docs/rule-pack-authoring.md`);
  authoring UI deferred pending saro-screen-review (D7).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
