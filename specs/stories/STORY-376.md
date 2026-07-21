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

## DELTA on RPV-001/002 (not a rebuild)
Immutable hash-chained snapshots, the draft-blocks-publish gate, publish
auditing, and attestation version+hash pinning **already existed**. This story
adds the missing lifecycle pieces: an explicit validation stage, tenant version
pinning, the immutability regression test, and the authoring guide.

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_validation_defers_the_fp_fn_verdict_rather_than_fabricating_it`, `test_lifecycle_states_are_ordered_draft_validation_published` | `services/rule_pack_lifecycle.py::validate_working_copy` |
| AC-2 | `test_publishing_a_new_version_does_not_alter_a_prior_pinned_version` | RPV-002 snapshot immutability (verified for this workflow) |
| AC-3 | `test_tenant_can_be_pinned_to_a_published_version`, `test_pinning_an_unpublished_version_is_refused`, `test_repinning_moves_the_tenant_without_deleting_the_old_version`, `test_pinned_tenant_resolves_to_its_pin_not_latest` | `models.TenantRulePackPin`, migration 039, `rule_pack_lifecycle.pin_tenant_version` |
| AC-4 | `test_pin_change_is_audited_as_a_rule_pack_change` (+ publish audit already in `rule_pack_versions.py`) | RULE_PACK_CHANGE on pin and publish |
| AC-5 | `test_authoring_guide_exists_and_states_immutability`, `test_authoring_guide_is_honest_about_the_pending_fp_fn_bar` | `docs/rule-pack-authoring.md`; UI deferred (D7) |

## The honest part — validation cannot fully work yet
AC-1 asks validation to report FP/FN against the Epic 18 bar. **That bar is
STORY-377 (human-gated, unsigned) and its harness is STORY-378 (not built).** So
`validate_working_copy` reports the structural readiness it *can* compute
(would-block draft rows, framework counts) and marks the FP/FN verdict
`bar_pending:STORY-377` — deferred, explicitly not passed. A stage returning
"looks good" without measuring FP/FN would assert something it cannot know.

## Design notes
- **Deprecation = re-pin, never delete.** A published snapshot is immutable
  (INV-7); a tenant moves versions by re-pinning, and the version it leaves —
  plus every attestation under it — stays intact. Pinning to an unpublished
  version is refused.
- **Pin changes are audited** (RULE_PACK_CHANGE) — changing a tenant's version
  changes which rules judge its evidence.
- `tenant_rule_pack_pins` carries RLS (migration 039) and is registered in the
  tenant-isolation census — the census guard caught its omission.
