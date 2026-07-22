# Story Pack — Commercial Readiness (Pack Epics 14–19, STORY-358..383)

**Source:** `SARO-Story-Pack-Epics-14-19.md` (authored outside repo; ingested 2026-07-20)
**Convention:** this file is the **canonical status ledger** for this pack. See
[Status ledger rules](#status-ledger-rules) — enforced by
`scripts/check_story_index.py` in CI, not by convention.

> Naming note: the repo previously used "Epic 14" for the governance runtime
> (STORY-400..404). This pack's epic numbers are tracked as **Pack Epics 14–19**;
> story IDs 358..383 were unused and are kept as-is.

---

## Status ledger rules

The repo is the only ledger that counts. Chat history and planning documents are
**hypotheses** until the repo confirms them.

| Status | Means | Evidence required |
|---|---|---|
| `IMPLEMENTED` | Code/artifact exists and is committed on a branch | ≥1 resolvable commit SHA |
| `MERGED` | Landed on `main` | ≥1 resolvable commit SHA |
| `DRAFTED` | A document/spec was written — **not shipped work** | must NOT cite a commit |
| `SPECIFIED` | Acceptance criteria written, implementation not started | must NOT cite a commit |
| `PLANNED` | Sequenced, not yet specified | must NOT cite a commit |
| `PREMISE-UNVERIFIED` | Depends on an artifact not yet verified in-repo | must NOT cite a commit |
| `BLOCKED` | Waiting on a human gate or external dependency | must NOT cite a commit |

**Deliberately absent: "done" and "complete."** Those words are what let *a
backlog was drafted* get remembered as *the backlog shipped*. Use `DRAFTED` for
documents and `IMPLEMENTED`/`MERGED` for code.

A story's Definition of Done includes updating its row **in the same PR** that
implements it. Status updates deferred to "later" are the drift mechanism.

---

## Premise verification (run before authoring dependent work)

Every reference this pack made to a prior artifact, checked against the repo:

| Pack claimed | Verified? | Repo reality |
|---|---|---|
| Epic 13 = STORY-340..357 exists | ❌ **FALSE** | No such story files. `specs/stories/` jumps 338 → 400. |
| "Validation strategy v1.1" | ❌ **FALSE** | No such document. |
| "20k Evidence Corpus Factory" | ❌ **FALSE** | No such corpus. |
| Four labeled ground-truth tiers | ❌ **FALSE** | Do not exist. STORY-377 must **create** them. |
| `RP-OBS-COMPLETE@1.0.0` published | ❌ **FALSE at ingest** | STORY-406 deferred it ("Wave 1/2 follow-on"). Built as PREREQ-RP → `rule_packs/observation/rp_obs_complete/1.0.0/pack.yaml` |
| `RP-TOOL-SCOPE@1.0.0` published | ❌ **FALSE at ingest** | Same. Built as PREREQ-RP. |
| Bedrock adapter exists | ✅ | `adapters/bedrock/` (parse, records, replay, source), STORY-406..408 |
| "66-record synthetic corpus" | ⚠️ partial | Generator exists: `scripts/demo_corpus_builder.py` + `demo_manifest.yaml` (STORY-407). Record count is manifest-driven, not fixed at 66. |
| SOC 2 work from scratch | ⚠️ overlap | Type **II** workstream exists: `compliance/soc2/STORY-SOC-01/02`, `docs/soc2-readiness-roadmap-v1.0.md` → STORY-364 is a delta |
| IRP is an open gating gap | ⚠️ overlap | `docs/incident-response-plan.md` v1.0 exists; gap #1 closed by S-1202 → STORY-371 is a delta |
| Rule-pack immutability to build | ⚠️ overlap | RPV-001/002 shipped hash-chained snapshots + publish API → STORY-376 is a delta |

**Consequence:** Epic 18 stories *create* the validation bar rather than
completing prior work; STORY-380's "Epic 13 closure audit" documents the
numbering correction instead of triaging stories that never existed.

---

## Status

| Story | Title | Status | Evidence (commit / test) |
|---|---|---|---|
| PREREQ-RP | Genesis observation rule-packs | IMPLEMENTED | a27b8ef · `tests/test_prereq_rp_observation_packs.py` 22 pass |
| STORY-358 | Observation adapter contract | IMPLEMENTED | a0210bc · `tests/test_story358_adapter_contract.py` 12 pass |
| STORY-359 | Azure OpenAI adapter | IMPLEMENTED | 967dd52 · `tests/test_story359_azure_adapter.py` 31 pass · corpus 54 records |
| STORY-360 | Vertex AI adapter | IMPLEMENTED | ff94aee · `tests/test_story360_vertex_adapter.py` 30 pass · corpus 56 records |
| STORY-361 | Cross-adapter conformance suite | IMPLEMENTED | df606a7 · `tests/test_story361_conformance.py` 31 pass · 18 matrix checks, 0 fail |
| STORY-362 | Adapter capability matrix | IMPLEMENTED | e06ce24 · `tests/test_story362_capability_matrix.py` 19 pass · generated + CI freshness gate |
| STORY-363 | Secrets baseline + history remediation (P0) | IMPLEMENTED | 9a2fd4b · `tests/test_story363_secret_scanning.py` 3 pass · AC-4/AC-5 human-gated |
| STORY-364 | SOC 2 control inventory (delta) | SPECIFIED | — |
| STORY-365 | Threat model + hardening pass | IMPLEMENTED | 85d22b1 · `tests/test_story365_route_authz.py` 5 pass |
| STORY-366 | Admin/config audit log | IMPLEMENTED | eb573c9 · `tests/test_story366_admin_audit_coverage.py` 7 pass |
| STORY-367 | Dependency/container scanning | IMPLEMENTED | 034b5ff · pip-audit green w/ waiver; npm prod gate exit 0 |
| STORY-368 | Monitoring, alerting, canary | IMPLEMENTED | 52da248 · `tests/test_story368_monitoring.py` 26 pass · AC-3 channel human-gated |
| STORY-369 | SLO definitions + SLA | IMPLEMENTED | bb1f3d3 · `tests/test_story369_slo_sla.py` 20 pass · SLA DRAFT, blocked by FND-064 |
| STORY-370 | DR + verified restore | IMPLEMENTED | 67bf85a · `tests/test_story370_restore_integrity.py` 18 pass · AC-4 rehearsal human-gated |
| STORY-371 | Support model + IRP (delta) | IMPLEMENTED | 14e519f · `tests/test_story371_support_model.py` 19 pass + FND-064 regression 12 pass |
| STORY-372 | Status + degradation comms | IMPLEMENTED | a4b1ce9 · `tests/test_story372_status_page.py` 16 pass · browser-verified 3 states |
| STORY-373 | Tenant onboarding + provisioning | IMPLEMENTED | db3a488 · `tests/test_story373_tenant_provisioning.py` 18 pass |
| STORY-374 | Usage metering + billing export (delta) | IMPLEMENTED | 6d77268 · `tests/test_story374_metering_export.py` 12 pass |
| STORY-375 | Versioned release process | IMPLEMENTED | b0cca87 · `tests/test_story375_release_process.py` 15 pass · rehearsal human-gated |
| STORY-376 | Rule-pack authoring workflow (delta) | IMPLEMENTED | 65f7b8f · `tests/test_story376_rule_pack_lifecycle.py` 12 pass · FP/FN validation blocked on STORY-377 |
| STORY-377 | Oracle completion bar (FP/FN) | IMPLEMENTED | 0790f3c · `tests/test_story377_completion_bar.py` 12 pass · SIGNED 2026-07-21 Profile A (recall-weighted) |
| STORY-378 | Confusion-matrix harness | IMPLEMENTED | a28d3a2 · `tests/test_story378_confusion_harness.py` 10 pass · enforcing Profile A on T1 (pass); caught FND-068 |
| STORY-379 | Validation report generator | IMPLEMENTED | 06a4556 · `tests/test_story379_validation_report.py` 17 pass · md+pdf, generated from 378 artifact |
| STORY-380 | Epic 13 closure audit (corrected) | IMPLEMENTED | a1caf9c · `tests/test_story380_epic13_closure.py` 10 pass · numbering correction recorded |
| STORY-381 | Privacy-safe product analytics | IMPLEMENTED | 701431f · `tests/test_story381_product_analytics.py` 27 pass · PHI-free by construction |
| STORY-382 | Pilot feedback intake | SPECIFIED | — |
| STORY-383 | Feedback → roadmap traceability | SPECIFIED | — |

Spec files for all 26 stories: a16ef50 (authored — `DRAFTED` work, which is why
those rows read `SPECIFIED`, not `IMPLEMENTED`).

### Security work carried in this batch (not from the pack)

| Item | Title | Status | Evidence |
|---|---|---|---|
| TM-F1 / FND-061 | HMAC-signed single-use Jira OAuth state | IMPLEMENTED | b82755b · `tests/regression/test_fnd_061_jira_oauth_signed_state.py` 11 pass |

TM-F1 was found by STORY-365's route-authz probe: the Jira OAuth callback bound
exchanged tokens to a tenant id taken from an **unsigned, attacker-controllable**
`state` param — a tenant-isolation (INV-3) break, not an OAuth hygiene issue.
Prioritised ahead of STORY-359 at the owner's direction.

**FND-063 remains OPEN:** `/oauth/jira/start` has no role/read-only gate
(pre-existing, logged in `quality/findings.md`).

---

## Sequencing (repo-adjusted)

1. **Security/ops floor:** 363 ✅, 365 ✅, 367 ✅, 366 ✅, 368, 371-delta, 372
2. **Adapter track:** 358 ✅ → PREREQ-RP ✅ → 359 → 360 → 361 → 362
3. **Validation track:** 377 (proposal, human sign-off gate) → 378 → 379 → 380
4. **Productization:** 373, 374, 375, 376-delta
5. **Feedback:** 381, 382, 383

## Human gates (OPEN until the owner acts — never auto-executed)

| Gate | Story | Recommendation |
|---|---|---|
| Rotate FND-003 credential in prod; verify old credential dead | 363 AC-4 | Do this first — rotation is the real control for a public-repo exposure |
| History scrub vs repo re-cut decision | 363 AC-5 | Rotate-only now; revisit before any visibility change |
| DR restore rehearsal (scratch project only) | 370 AC-4 | Never against prod |
| ~~FP/FN threshold sign-off~~ | 377 AC-3 | **SIGNED 2026-07-21 — Profile A** (recall-weighted, per-pack precision floor, T4 blank/revisit conditions) |
| Alert channel / status page / uptime SaaS signup | 368, 372 | Options documented; no accounts created |
