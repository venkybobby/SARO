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

## STORY-362 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| Conformance report (source for scenario rows) | ✅ | `quality/conformance/adapter-conformance.json` (df606a7) |
| Field-mapping tables | ✅ | `docs/adapter-design.md` §3.1–3.3 |
| Language guardrails | ✅ | `docs/compliance-claims.md` (certification/conformity prohibitions) |
| **AC-3 "linked from README"** | ❌ **PREMISE-UNVERIFIED** | **No root `README.md` exists in this repo.** Linked instead from `compliance/README.md` (Compliance Hub docs area) and `docs/adapter-design.md`. Flagged for the owner rather than inventing a root README as a side effect of this story. |

## Decision Log — STORY-362 (appended)
- D20 Q: Hand-author the matrix with a freshness check (AC-1 allows it) or
  generate it? → **Generate.** Field rows are read from each adapter parsing its
  provider's STOCK log shape, so the doc changes when behaviour changes. Prose
  tables drift optimistically: nobody forgets to add a capability they shipped;
  everybody forgets to remove one they didn't.
- D21 Q: Azure happy-path fixture includes token counts (some configs report
  them) — use it for field coverage? → **No.** Added
  `standard_schema_record()` per provider = the provider's minimum guaranteed
  shape. A buyer must not read "✅ token counts" and discover it depended on a
  non-default configuration. Azure/Vertex tokens therefore render ❌/◐, not ✅.
- D22 Q: Enforce claim language by review? → Generator refuses to write output
  containing prohibited phrases (certified/compliant/conformity assessment) →
  the guardrail runs on every regeneration instead of relying on a reader.

## STORY-361 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| Bedrock adapter | ✅ | `adapters/bedrock/parse.py::parse_envelope` |
| Azure adapter | ✅ | `adapters/azure_openai/parse.py` (967dd52) |
| Vertex adapter | ✅ | `adapters/vertex_ai/parse.py` (ff94aee) |
| Both genesis packs | ✅ | `rule_packs/observation/*/1.0.0/pack.yaml` (a27b8ef) |
| "How to add adapter #N" §4 | ✅ | `docs/adapter-design.md` (a0210bc) — extended by AC-4 |

## Decision Log — STORY-361 (appended)
- D17 Q: Adapters genuinely differ in what their logs express (no tool data or
  stop reason on Azure/Vertex). Fail them, or skip? → **Neither.** A provider
  must return an outcome for every scenario; it may declare `NOT_SUPPORTED` but
  only with a written reason ≥20 chars, and gaps render as `⚠️ n/a` in the
  matrix, never as a tick → a limitation is visible instead of becoming either
  a permanent red build or invisible green.
- D18 Q: What stops an adapter declaring its way out of a scenario later? →
  `test_known_gaps_are_exactly_the_expected_ones` pins the current gap set, so a
  NEW gap is a deliberate reviewed change, not a quiet regression.
- D19 Q: Build scenario records directly, or through each adapter's parser? →
  Through the real parser. Hand-built records would test the contract (already
  covered) and prove nothing about parsing.

## Deviation — STORY-360: INV-1 guard false positive
The STORY-336 no-external-model guard flagged `aiplatform.googleapis.com` in
`adapters/vertex_ai/records.py`. Correct detection, wrong conclusion: the string
is a Cloud Audit Log `serviceName` **discriminator** (which entries to interpret),
never a call target — the adapter imports no GCP SDK and reads customer-owned
exports only.

Options considered:
- File-level DEFAULT_ALLOWLIST entry → **rejected**: exempts the file from the
  whole scan, including SDK-import detection, which is the guard's real control.
  A later `import google.generativeai` there would pass unnoticed.
- Obfuscate the literal (split/derive/move to YAML) → **rejected**: hiding from
  a security guard rather than answering it, and it would leave the next reader
  with a constant whose shape exists only to dodge a check.
- Conservative choice (taken): add `ENDPOINT_LITERAL_EXEMPTIONS`, keyed by
  (path, endpoint) with a written reason. Exempts ONE string in ONE file;
  imports and all other literals in that file remain scanned. Backed by a test
  proving the adapter imports no GCP SDK, so the exemption rests on evidence.

## STORY-360 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| `NormalizedInvocationRecord` | ✅ | `adapters/contract.py` (a0210bc) |
| Both genesis packs | ✅ | `rule_packs/observation/*/1.0.0/pack.yaml` (a27b8ef) |
| Adapter #2 pattern to mirror | ✅ | `adapters/azure_openai/` (967dd52) |
| Corpus-builder determinism pattern | ✅ | `scripts/azure_corpus_builder.py` (967dd52) |

## Decision Log — STORY-360 (appended)
- D14 Q: Duplicate the tenant-scoping reader per adapter, or extract it? →
  Extract `adapters/export_source.py` (scope enforcement, traversal rejection,
  segment-boundary prefix match, NDJSON/array/wrapper iteration) → an INV-3 fix
  has one home instead of N; docs promise adapters "conform to the contract, not
  fork it". Azure's public API preserved; its 31 tests are the safety net.
- D15 Q: Vertex Cloud Audit **Data Access** logs may contain
  `protoPayload.request` / `.response` — for generative calls that IS the prompt
  and the model output (real PHI, unlike Azure where no payload exists). Read or
  refuse? → **Refuse by construction.** The parser never touches those keys, and
  a test feeds a record with PHI-shaped payloads present and asserts nothing
  reaches the normalized record → INV-2 is proven under the hostile case, not
  merely absent-by-luck.
- D16 Q: Endpoint-deployed models expose `endpoints/{id}`, not a model name →
  model identity genuinely unknowable from the log → mark MISSING and disclose
  in the capability matrix; do NOT pass an endpoint id off as a model id (it
  would make a model allowlist rule meaningless while looking like it works).

## Gate defect found in use (self-inflicted, worth recording)
Amending the STORY-359 commit invalidated the SHA the index had just cited — and
`check_story_index.py` still passed, because it verified the SHA *existed*
(`git cat-file`) rather than that it was *reachable from HEAD*. Amended-away,
reset, and abandoned-worktree commits all linger in the object store until gc,
so the gate would accept evidence pointing at nothing in the branch history —
the exact class of drift it exists to prevent. Fixed by adding a
`git merge-base --is-ancestor` reachability check + regression test.
Practical consequence: the index row is committed as its own follow-up commit
in the same PR (amending to embed its own SHA is an infinite regress).

## STORY-359 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| `NormalizedInvocationRecord` | ✅ | `adapters/contract.py` (a0210bc) |
| RP-OBS-COMPLETE@1.0.0 | ✅ | `rule_packs/observation/rp_obs_complete/1.0.0/pack.yaml` (a27b8ef) |
| RP-TOOL-SCOPE@1.0.0 | ✅ | `rule_packs/observation/rp_tool_scope/1.0.0/pack.yaml` (a27b8ef) |
| Bedrock corpus scenarios to mirror | ✅ | `scripts/demo_corpus_builder.py` (manifest-driven, `_det_uuid4` determinism) |
| Tenant-isolation precedent | ✅ | `adapters/bedrock/source.py::S3LogStore.for_tenant`, `models.TenantLogSourceConfig` |
| Adapter design doc | ✅ | `docs/adapter-design.md` (a0210bc) |

## Decision Log — STORY-359 (appended)
- D11 Q: Azure logs carry no tool/function data and no guaranteed token counts —
  fake coverage or expose the gap? → Expose: mark structurally UNAVAILABLE, and
  make RP-TOOL-SCOPE's silence on Azure explicitly *tested and documented* →
  zero findings from absent data must never be read as "clean"; capability
  matrix (362) gets honest "not supported" rows.
- D12 Q: Tenancy source for Azure records? → Operator config ONLY. Azure records
  contain subscription GUIDs / objectId / (some schemas) an Entra tenant id;
  none may set SARO tenancy → pinned by a test that feeds a hostile record
  claiming another tenant (INV-3).
- D13 Q: Ingestion surface? → Customer-owned export reader over files (D6), with
  container+prefix scoping and traversal rejection → testable with zero cloud
  calls; mirrors Bedrock's read-only posture without inventing an Azure SDK dep.

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
