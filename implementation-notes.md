# STORY-RPV-002 — Attestation Evidence Pins Rule-Pack Version
Stage: standard

## Lifecycle
- [x] discover   (recon: grc/evidence.py capture + hash chain (_PAYLOAD_FIELDS, per-tenant seq),
                  grc/orchestrator.run_audit, grc/citation.py -> checks use a STATIC crosswalk
                  (framework_crosswalk.json), NOT the DB rule tables; RPV-001 snapshot service/table)
- [x] shape      (skipped brainstorm — STORY has ACs; interview -> Decision Log below)
- [x] preview    (skipped — backend-only; customer UI for criteria reproduction is out-of-scope)
- [x] plan
- [x] build
- [x] verify    (change-debrief.html generated)
- [x] sell       (n/a)

## Decision Log
Q1 what does the pin attach to? → grc_evidence_records gets rule_pack_version_id +
  rule_pack_content_hash, added to _PAYLOAD_FIELDS so the pin is inside the record's own
  content_hash / chain (AC-1: criteria pin is tamper-evident). Resolved at capture time (persist).

Q2 does the pin change what the checks evaluate? → NO. GRC checks resolve against the static
  versioned crosswalk (grc/citation.py, framework_crosswalk.json), never the working-copy DB rule
  tables — so "working-copy rules must never be the evaluation basis" (AC-2) already holds for the
  audit path. The pin is a provenance annotation + an evaluation gate, not a check-logic rewrite.

Q3 STRICT vs PERMISSIVE default (owner-locked PERMISSIVE)? → config saro_rule_pack_eval_mode,
  default "PERMISSIVE". PERMISSIVE pins the latest PUBLISHED snapshot (never the working copy);
  if none published, pin = None (pre-versioning, evaluation still proceeds). STRICT refuses to
  evaluate when no version is published OR the working copy has drifted from the latest published
  beyond tolerance (default: any diff). Resolver is called per-invocation (AC-5).

Q4 integrity at pin time (edge)? → resolver verifies the latest snapshot's chain before pinning;
  a broken chain REFUSES in BOTH modes (RulePackIntegrityError) — this is an incident, not a warning.

Q5 how is "full rule content of the pinned version" reproduced (AC-3)? → RPV-001 stored only a
  hash manifest (no full text). Extend the snapshot with snapshot_content JSONB ({table:{id:{fields}}})
  populated at publish, so reproduction returns the EXACT frozen rule text even after the working
  copy mutates. content_hash/manifest (RPV-001) unchanged. reproduce_criteria re-hashes each stored
  row (_hash_row_payload) and cross-checks it against the chain-covered manifest, so snapshot_content
  cannot be tampered independently of the chain (see DEV-2). Rule packs are tiny (~160 rows) so
  full-content storage is cheap.

Q6 pre-existing records (AC-4)? → rule_pack_version_id NULL is rendered verbatim as "PRE-VERSIONING"
  by the criteria-reproduction API; NEVER backfilled with a guessed version. The API states the
  limitation in its response (honest-gap disclosure).

Q7 caching (AC-5)? → a version-keyed immutable lru cache of reproduced content is permitted;
  NEVER key any cache on payload-derived input. Resolver reads latest snapshot per call.

## Deviations
- DEV-1 (reviewer B1): first cut added the pin to _PAYLOAD_FIELDS unconditionally, which
  false-failed verification of every pre-RPV-002 evidence record (AC-4 violation).
  Conservative fix: pin fields live in _PIN_FIELDS and are folded into the canonical
  payload ONLY when non-NULL, so legacy/NULL-pin records serialize identically to before.
  Pinned by FND-041.
- DEV-2 (reviewer B2): first cut left snapshot_content outside the hash chain (the Q5 note
  claimed a cross-check that did not exist — corrected above). Fix: reproduce_criteria
  re-hashes stored rows against the chain-covered manifest and refuses/flags on mismatch
  (content_integrity=False). Pinned by FND-040.

## Review outcomes (both agents, addressed in-PR)
- Reviewer VERDICT: REQUEST-CHANGES -> B1 (FND-041) + B2 (FND-040) fixed with pinning
  regression tests; S1 (regression pins) satisfied. N1/N2 documented (whole-chain vs
  per-version verify status; content_integrity now surfaced alongside pin_matches_snapshot).
- Security-auditor VERDICT: PASS -> 2 Should-fix pinned: cross-tenant 404 test + route-ordering
  test (tests/test_rpv_version_pin_api.py). N3/N4 doc notes accepted.
