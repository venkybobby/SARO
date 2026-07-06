# STORY-RPV-002 — Attestation Evidence Pins Rule-Pack Version

Epic: Rule-Pack Versioning | Priority: P0 | Depends: STORY-RPV-001
Origin: Gap #1 — without version pinning, evidence integrity covers the record
but not the criteria; zero-PHI retention means no re-evaluation is possible, so
the pin is the ONLY link between an attestation and its criteria.

## User Story
As a Compliance Lead responding to an examiner, I need every attestation and
evidence record to carry the rule-pack version (and hash) it was evaluated
against, so I can produce the exact criteria for any historical attestation on
demand.

## Acceptance Criteria

AC-1
Given an evaluation executes, When its evidence record is persisted, Then the
record includes rule_pack_version_id and rule_pack_content_hash from the
snapshot in force, included in the fields covered by the record's own hash
chain (criteria pin becomes tamper-evident).

AC-2
Given the evaluation engine starts an evaluation, When no published rule-pack
version exists or the working copy has drifted from the latest published
version beyond configured tolerance, Then behavior follows an explicit config:
STRICT (refuse to evaluate) or PERMISSIVE (evaluate against latest published
snapshot only — never the working copy). Working-copy rules must never be the
evaluation basis once this story ships. (Interacts with STORY-CHUB-011 AC-5:
that story's status filter becomes obsolete for the eval path; snapshot
membership supersedes it.)

AC-3
Given a historical evidence record, When a "criteria reproduction" request is
made (API + internal tool), Then SARO returns the full rule content of the
pinned version for the frameworks in scope of that record, with chain
verification status.

AC-4
Given pre-existing evidence records (created before this story), When queried,
Then they report rule_pack_version_id = NULL rendered explicitly as
"PRE-VERSIONING" — never backfilled with a guessed version. Honest-gap
disclosure: the criteria-reproduction API states this limitation verbatim.

AC-5
Given the stateless core (INV-4), When version pinning is implemented, Then the
snapshot reference is resolved per evaluation invocation with no cross-request
mutable caching of rule content keyed on anything payload-derived; a
version-keyed immutable cache is permitted.

## Edge Cases
- Version published mid-evaluation-batch: all evaluations in one invocation
  pin the version resolved at invocation start — no mixed-version batches
- Snapshot verification fails at pin time (tampered/broken chain): evaluation
  refuses in both STRICT and PERMISSIVE modes; this is an incident, not a warning
- Multi-framework evaluation spanning frameworks with different latest
  versions: record pins one composite snapshot id, not per-framework ids
  (composite is what STORY-RPV-001 publishes)

## Out of Scope
- Re-evaluation/replay of historical observations (impossible by design —
  zero retention; document in product limitations instead)
- Customer UI for criteria reproduction (follow-on; API first)

## NFRs
- Version resolution adds < 5ms p99 to evaluation-path latency
- Criteria reproduction responds < 2s for any single record

## Traceability
| Item | Reference |
|---|---|
| Snapshot mechanism | STORY-RPV-001 |
| Stateless core invariant | INV-4 (invariant-reviewer) |
| Evidence hash chain | Existing evidence-record integrity design (SEC Proof lineage) |
| Honest-gap disclosure | Gap #4 pattern; synthetic-examiner Phase 4 |
| Examiner question | "Which rule version did this attestation use?" |
