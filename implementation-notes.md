# Epics 14-19 Story Pack (STORY-358..383) — Commercial Readiness Batch
Stage: standard

## Lifecycle
- [x] discover   (recon done: pack vs repo ground truth — see Recon Findings below)
- [x] shape      (pack is fully specified w/ ACs; interview self-answered with
                  conservative defaults, user away — see Decision Log; user-gated
                  decisions explicitly marked OPEN [HUMAN])
- [ ] preview    (deferred — UI surfaces (STORY-366 read view, STORY-382 widget)
                  ship backend-first; screens go through saro-screen-review before wiring)
- [x] plan       (execution order = pack's suggested sequencing adjusted for repo
                  reality; per-story delta plans in each spec file)
- [ ] build
- [ ] verify
- [ ] sell       (n/a — not partner-facing until user reviews)

## Recon Findings (pack assumptions vs repo ground truth)
1. **Pack assumption #1 is WRONG**: Epic 13 (STORY-340..357) does not exist in this
   repo — no specs, no "validation strategy v1.1", no "20k Evidence Corpus Factory",
   no labeled 4-tier corpus. Validation machinery that DOES exist: STORY-335..338
   (groundedness, no-external-model guard, claims guard, offline qa_lab).
2. **RP-OBS-COMPLETE / RP-TOOL-SCOPE do not exist** — STORY-406 explicitly deferred
   them ("Wave 1/2 follow-on", blocked by rule_packs/loader.py vs shipped-YAML schema
   mismatch). The envelope-rule mechanism (STORY-411, rule_packs/envelope_loader.py)
   is the right substrate. Building them is a PREREQ task.
3. **Bedrock adapter exists** (adapters/bedrock/: parse, records, replay, source;
   STORY-406..408) — Epic 14's premise holds. "66-record corpus" ≈ demo corpus
   builder (STORY-407, scripts/demo_corpus_builder.py + demo_manifest.yaml).
4. **Repo already used "Epic 14"** for governance runtime (STORY-400..404). Pack
   epics are tracked as "Pack Epics 14-19 (commercial readiness)" — story IDs
   358..383 are free and kept.
5. **Large overlaps — stories deliver DELTAS, not rebuilds:**
   - STORY-364 → compliance/soc2/STORY-SOC-02 control-evidence matrix +
     docs/soc2-readiness-roadmap-v1.0.md already exist (Type II workstream).
   - STORY-371 → docs/incident-response-plan.md v1.0 exists; gating gap #1
     already marked closed by S-1202 per GAP_ANALYSIS_2026-06-15.
   - STORY-376 → RPV-001/002 immutable hash-chained snapshots + publish API exist.
   - STORY-367 → security_scan.sh static patterns + quality-gates.yml exist;
     no gitleaks/osv/container scan.
   - STORY-363 → seed scripts already env-var-only (#119); FND-003 = the historic
     hardcoded-secret finding. No secret-scanning CI gate yet.
   - STORY-373 → scripts/seed_demo_tenant.py is the idempotent-provisioning seed.
   - STORY-365 → TENANT_ISOLATION.md + test_pt009 concurrency proof exist;
     no per-route authz probe matrix.

## Decision Log
- D1 Q: Story numbering vs repo collision? → Keep pack IDs 358..383 (range free); annotate epic-label distinction in every spec → specs carry a Ground Truth header.
- D2 Q: Missing genesis rule-packs? → Build RP-OBS-COMPLETE@1.0.0 + RP-TOOL-SCOPE@1.0.0 as envelope-style packs extending the STORY-411 loader (envelope-only fields, INV-2-safe) before adapter stories → new PREREQ-RP work item; no rewrite of legacy citation-pack loader.
- D3 Q: Rebuild vs delta on overlaps? → Delta-only; specs cite existing artifacts as evidence → no duplicate SOC/IRP/RPV artifacts.
- D4 Q: Branch/PR strategy for 26 stories? → Single batch branch story/epics-14-19-pack, conventional commit per story, one PR (precedent: PR #109 8-story batch) → reviewable per-commit; single CI run per push.
- D5 Q: User-gated actions (363 rotation+history scrub, 370 restore rehearsal, 377 threshold sign-off, external SaaS signups)? → Implement everything up to the gate; mark gate OPEN [HUMAN] in spec (SOC-01 pattern); never execute destructive/prod/external actions → stories close as "artifact done, human gate open".
- D6 Q: Azure/Vertex ingestion mode? → File/JSON-export readers (mirror-async), deterministic local parsing, customer-owned storage posture — mirrors Bedrock S3-layout reader; zero live cloud calls in tests → INV-1/INV-2/INV-6 clean.
- D7 Q: UI for 366/382? → Backend + API + tests now; UI wiring deferred pending screen review → logged as deviation, not silent scope cut.
- D8 Q: Normalized contract shape (358)? → Pydantic NormalizedInvocationRecord alongside (not replacing) frozen dataclass Envelope; Bedrock adapter emits it via a thin converter → attestation hashes unchanged, no hash-format bump.

## Build Log (live — updated as each story lands)
- STORY-363 ✅ gitleaks gate + canary self-test + secrets runbook (2 human gates OPEN).
- STORY-365 ✅ security headers, evaluate rate limit, route-authz probe suite,
  threat model + pentest scope. Found TM-F1 (Jira OAuth unsigned state) → task spawned.
- STORY-367 ✅ pip-audit/npm/trivy gates + waiver process w/ expiry enforcement.
  Triage: form-data fixed, ecdsa waived (no upstream fix), vite/vitest dev-chain
  waived → upgrade task spawned.
- STORY-366 ✅ audit coverage registry (unclassified route = failure) + instrumented
  role change / risk-config / tenant provisioning. Full suite 1656 pass.
- STORY-358 ✅ adapter contract (NormalizedInvocationRecord); INV-2 enforced by
  test; Bedrock lift additive, 53 corpus tests unchanged; docs/adapter-design.md.
- PREREQ-RP ✅ genesis observation packs RP-OBS-COMPLETE + RP-TOOL-SCOPE (a27b8ef).
- TM-F1/FND-061 ✅ merged in from claude/ecstatic-lamport-3c82c4 (b82755b) — HMAC
  signed single-use OAuth state. Prioritised ahead of STORY-359 at user's direction
  (tenant-isolation break outranks adapter breadth). FND-063 remains OPEN.
- LEDGER-DRIFT ⏳ process fix (user-directed): evidence-linked index + premise-check
  gate + closed status vocabulary + session-start ritual + DoD coupling.

## Decision Log — ledger-drift fix (appended)
- D9 Q: Where can the premise-check actually be enforced, given `saro-story-author`
  and `saro-invariant-audit` do NOT exist in this repo (.claude/agents/ has only
  reviewer.md + security-auditor.md)? → Enforce in the surfaces that DO execute:
  CLAUDE.md failure-mode table, saro-lifecycle PLAN stage, engineering-standards
  DoD, plus a mechanical CI gate (scripts/check_story_index.py) → the check runs
  on every PR instead of depending on an agent that isn't there. Report the
  missing agents rather than pretending to wire into them.
- D10 Q: Prose convention or executable gate for "no status without evidence"? →
  Executable: index rows with IMPLEMENTED/MERGED must cite a resolvable commit
  SHA; draft-class statuses must NOT cite one; vocabulary is closed (no
  "done"/"complete") → stale status fails CI rather than misleading a reader.

## Prior build notes
- specs: 26 story files + STORY-PACK-14-19-INDEX committed (a16ef50).
- STORY-363 build started: gitleaks config + canary fixture + CI job + secrets runbook.

## Deviations
None yet.
