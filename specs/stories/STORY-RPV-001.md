# STORY-RPV-001 — Versioned, Immutable Rule-Pack Snapshots

Epic: Rule-Pack Versioning (new) | Priority: P0 — examiner-facing gap
Origin: Gap #1 (radar scan #1 session, 2026-07-04) — rule rows were mutated in
place; historical attestations can no longer prove what rule text they were
evaluated against.

## User Story
As an AI Auditor persona, I need every rule-pack state to exist as an
immutable, hash-identified version, so that any historical attestation can be
traced to the exact rule content in force at evaluation time.

## Context / Approach
Reuse the proven hash-chain pattern from evf_qco_registry / evf_publication_events
(prev_hash + record_hash over immutable fields, trigger-enforced immutability).
Do NOT invent a new mechanism. Live tables (eu_ai_act_rules, governance_rules,
nist_ai_rmf_controls) become the "working copy"; publishing freezes a snapshot.

## Acceptance Criteria

AC-1
Given the current state of the rule tables, When a rule-pack version is
published, Then an immutable snapshot record is created containing: version id
(semver), content hash over all included rule rows (canonical serialization),
per-framework row counts, publisher, timestamp, and prev_version hash — chain
verifiable end-to-end.

AC-2
Given a published snapshot, When any write is attempted against it, Then the
write is rejected by database trigger (same enforcement style as
evf_engagement_transitions).

AC-3
Given publication, When validation_status is inspected, Then only
SME_VALIDATED rows are includable in a published snapshot; attempting to
publish with DRAFT_UNVALIDATED rows in scope fails with a listing of the
blocking rows. (LEGACY_UNREVIEWED handling: config flag — includable with a
version-level caveat field until the legacy review completes; caveat text
appears in the snapshot record.)

AC-4
Given the working-copy tables change after a publish (e.g., radar deltas),
When diffed against the latest snapshot, Then a machine-readable changelog
(added/updated/retired rule ids per framework) is producible on demand.

AC-5
Given snapshot verification, When the chain is recomputed from genesis, Then
any tampered snapshot is detected and identified by version id.

## Edge Cases
- Publishing with zero changes since last version → rejected (no empty versions)
- Rule row deleted from working copy → snapshot diff must show it as retired,
  not silently absent
- Hash canonicalization: column order, nulls, and text encoding must be
  deterministic — document the canonical form in the migration comment

## Out of Scope
- Evidence-record pinning to versions (STORY-RPV-002)
- UI for browsing versions/changelogs (follow-on)
- Customer-facing rule-pack subscription packaging (radar rule-pack product)

## NFRs
- Publish operation < 5s at 10x current rule volume
- Snapshot storage additive-only; no impact on evaluation-path read latency

## Traceability
| Item | Reference |
|---|---|
| Immutability pattern | evf_qco_registry, evf_publication_events (FR-EVF-10/20/21) |
| Status vocabulary | Migration radar_scan1_validation_status_columns |
| SME gate | GRC SME Validation Requirements |
| Examiner demand | synthetic-examiner Phase 3 (provenance, tamper-evidence) |
