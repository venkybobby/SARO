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
| # | Question | Answer (conservative default) | Consequence |
|---|---|---|---|
| D1 | Story numbering vs repo collision? | Keep pack IDs 358..383 (range free); annotate epic-label distinction in every spec | Specs carry a Ground Truth header |
| D2 | Missing genesis rule-packs? | Build RP-OBS-COMPLETE@1.0.0 + RP-TOOL-SCOPE@1.0.0 as envelope-style packs extending the STORY-411 loader (envelope-only fields, INV-2-safe) before adapter stories | New prereq work item; no loader/schema rewrite of legacy citation packs |
| D3 | Rebuild vs delta on overlaps? | Delta-only; specs cite existing artifacts as evidence | No duplicate SOC/IRP/RPV artifacts |
| D4 | Branch/PR strategy for 26 stories? | Single batch branch story/epics-14-19-pack, conventional commit per story, one PR (precedent: PR #109 8-story batch) | Reviewable per-commit; single CI run per push |
| D5 | User-gated actions (363 rotation+history scrub, 370 restore rehearsal, 377 threshold sign-off, external SaaS signups) | Implement everything up to the gate; mark gate OPEN [HUMAN] in spec (SOC-01 pattern); never execute destructive/prod/external actions | Stories close as "artifact done, human gate open" where applicable |
| D6 | Azure/Vertex ingestion mode? | File/JSON-export readers (mirror-async), deterministic local parsing, customer-owned storage posture — mirrors Bedrock S3-layout reader; zero live cloud API calls in tests | INV-1/INV-2/INV-6 clean; moto-style fixtures unnecessary |
| D7 | UI for 366/382? | Backend + API + tests now; UI wiring deferred pending screen review | Logged as deviation, not silent scope cut |
| D8 | Normalized contract shape (358)? | Pydantic model NormalizedInvocationRecord alongside (not replacing) frozen dataclass Envelope; Bedrock adapter emits it via a thin converter — attestation hashes unchanged | No hash-format bump needed |

## Deviations
None yet.
