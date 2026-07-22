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

## Gate defect #2 found in use — all-digit SHAs (self-inflicted)
`check_story_index.py` filtered SHA candidates with `not s.isdigit()`, intended
to stop prose numbers being read as commits. But ~1 in 27 short SHAs is all
decimal digits ((10/16)**7 ≈ 3.7%), and HEAD happened to be `9410176` — so the
gate reported a *correctly evidenced* row as unevidenced. Found because a test
generated its fixture from real HEAD rather than a hardcoded SHA.

Fix: stop guessing which tokens are SHAs; ask git. Candidates are hex-shaped
tokens, and only those that RESOLVE count. Draft-row over-claim detection also
now counts only resolvable commits, so a stray 7-digit number in prose is not
mistaken for shipped-work evidence.

Second lesson: this gate has now had two defects (existence-vs-reachability,
all-digit SHAs), both found by using it rather than by reading it. Its tests
generating fixtures from live git state — not fixed strings — is what surfaced
both.

## STORY-380 — premise check (PLAN stage 3a) — the numbering-correction story
| Referenced artifact | Verified? | Path |
|---|---|---|
| "Epic 13 = STORY-340..357" | ❌ never existed | the whole point of this story: audit the ACTUAL validation machinery, record the correction |
| Actual validation machinery | ✅ | STORY-335 (groundedness), 336 (no-external-model guard), 337 (claims guard), 338 (offline qa_lab), + this pack's 377/378/379 |
| Validation artifacts to link | ✅ | validation-strategy-v1.0, completion-bar.proposed.yaml, confusion-latest.json, validation-report.{md,pdf} |

## Decision Log — STORY-380 (appended)
- D69 Q: Triage STORY-340..357? → They do not exist. This audit instead
  triages the validation-adjacent work that DOES exist (335..338 + the pack's
  377/378/379), each Done/Superseded/Dropped with an evidence link, and records
  the numbering correction so no future plan re-assumes Epic 13.
- D70 Q: Close it as "done"? → No — closed as a one-page audit with honest
  open-items pointing at the human gate (377 sign-off) rather than claiming
  completeness the validation track does not yet have.

## STORY-379 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| 378 confusion-matrix artifact (source of numbers) | ✅ | `quality/validation/confusion-latest.json` (a28d3a2) |
| fpdf2 PDF pattern | ✅ | `scripts/generate_governance_pdfs.py` |
| Language guardrails | ✅ | `docs/compliance-claims.md` forbidden phrases |
| Bar status (for the Limitations honesty) | ✅ | `services/validation_bar.py` |

## Decision Log — STORY-379 (appended)
- D66 Q: Numbers hand-typed or generated? → **Generated from the 378 artifact.**
  A test asserts changing the JSON changes the report — generation is the
  anti-drift control, and the report cannot claim a rate the harness did not
  measure (AC-1).
- D67 Q: Limitations tone? → **Derived and deliberately unflattering.** The
  section is computed from the actual state (only T1 measured, bar unsigned, 2
  packs, synthetic corpus) — understatement over overstatement. A perfect T1
  score is stated AS a narrow synthetic result, not as broad validation.
- D68 Q: Overclaim guard? → Generator refuses to emit certified/compliant/client
  results (same closed list as the capability-matrix generator); parametrized
  test proves each phrase trips it.

## STORY-378 — premise check (PLAN stage 3a) — report-only (377 unsigned)
| Referenced artifact | Verified? | Path |
|---|---|---|
| The bar (report-only source) | ✅ | `services/validation_bar.py` — returns None unsigned (0790f3c) |
| Deterministic evaluate (INV-1) | ✅ | `rule_packs/observation/evaluate.py` — pure, no model calls |
| Packs to score | ✅ | RP-OBS-COMPLETE / RP-TOOL-SCOPE (a27b8ef) |
| Labeled ground truth | ❌ **must build** | corpora are planted but carry no per-rule labels; a confusion matrix needs them |

## Decision Log — STORY-378 (appended)
- D62 Q: Where does ground truth come from? → A **labeled T1 corpus** where each
  record carries the rule_ids that SHOULD fire. Built deterministically (a
  builder + `--check`), so the matrix is reproducible run-to-run (AC-1).
- D63 Q: Enforce or report? → **Report-only until 377 is signed.** The harness
  reads `validation_bar.active_thresholds()`; None ⇒ it emits rates with NO
  pass/fail. It can NEVER enforce an unsigned bar — that guarantee lives in
  validation_bar, and a test pins that the CI gate stays advisory while unsigned.
- D64 Q: User is deciding the profile concurrently. → Building report-only means
  the harness tells them the ACTUAL rates BEFORE they pick a profile, and signing
  later flips it to enforcing with no code change.
- D65 Q: Matrix granularity? → Per pack, per tier, per rule: TP/FP/FN/TN →
  precision/recall/F1. Versioned JSON artifact + appended trend.jsonl (AC-2/AC-4).

## STORY-377 — premise check (PLAN stage 3a) — HUMAN-GATED
| Referenced artifact | Verified? | Path / finding |
|---|---|---|
| "validation strategy v1.1" (four tiers) | ❌ never existed | premise table already recorded this; I create **v1.0** and note the numbering correction (pack said v1.2) |
| RP-OBS-COMPLETE / RP-TOOL-SCOPE (bar applies to) | ✅ | `rule_packs/observation/*/1.0.0/pack.yaml` (a27b8ef) |
| Offline qa_lab labeled tier (T3) | ✅ | `qa_lab/labeling.py` (STORY-338) |
| Synthetic corpora (T1/T2) | ✅ | `tests/fixtures/{azure,vertex}/corpus.ndjson` |
| 378 harness / 376 validate consume the bar | ✅ | both reference `bar_pending:STORY-377` |

## Decision Log — STORY-377 (appended)
- D59 Q: Pick the thresholds myself? → **NO — AC-3 forbids it.** These are a
  product decision. I PROPOSE numbers with rationale + tradeoffs; the sign-off is
  `[HUMAN — OPEN]`. Structural guarantee: the machine-readable bar carries
  `status: PROPOSED_AWAITING_SIGNOFF`, and a test asserts it is NOT signed — so
  nothing (378 harness, 376 validate) can enforce an unsigned bar.
- D60 Q: The FP/FN asymmetry — decide it? → No, it is THE key product tradeoff.
  For an evidence tool a false NEGATIVE (missing a real gap → claiming coverage
  we lack) is arguably worse than a false POSITIVE (wasting a reviewer's time),
  which argues for recall-weighting — but that is the owner's call. So I present
  **two candidate profiles** (recall-weighted vs balanced) and ask them to pick,
  rather than embedding my choice.
- D61 Q: Version? → v1.0 (v1.1 never existed). Record the correction so a future
  pack does not re-assume v1.1/v1.2.

## STORY-376 — premise check (PLAN stage 3a) — DELTA on RPV-001/002
| Referenced artifact | Verified? | Path / finding |
|---|---|---|
| Immutable published snapshots (INV-7) | ✅ done | `models.RulePackSnapshot` (published-on-create, hash-chained, DB trigger migration 028 rejects UPDATE/DELETE) |
| draft→published gate | ✅ partial | `_classify` blocks DRAFT_UNVALIDATED/NULL rows from publish; `validation_status` lifecycle on rule tables |
| Publish audits (AC-4) | ✅ **already done** | `routers/rule_pack_versions.py:98` writes RULE_PACK_CHANGE on publish |
| Attestation pins version+hash (AC-2) | ✅ exists | RPV-002 pins version + content_hash on evidence |
| Tenant version pinning (AC-3) | ❌ **absent** | no tenant→published-version binding exists |
| Validation stage reporting FP/FN (AC-1) | ❌ blocked | the FP/FN **bar is STORY-377 (human-gated) and the harness is 378 (not built)** |

## Decision Log — STORY-376 (appended)
- D55 Q: Rebuild snapshots? → No — RPV-001/002 already give immutable
  hash-chained snapshots + publish auditing + attestation pinning. Delta only:
  tenant pinning, an explicit validation stage, the immutability regression test,
  the authoring guide.
- D56 Q: Validation stage FP/FN? → **Cannot fully implement — depends on the
  un-built, human-gated Epic 18 bar (377/378).** Build the stage to report
  structural readiness (would-block draft rows, counts) and mark the FP/FN
  verdict explicitly `bar_pending: STORY-377` rather than fabricating a number.
  This is the honest version of AC-1, not a stub pretending to be the whole.
- D57 Q: Deprecation/rollback (AC-3)? → A subscribing tenant **pins** a published
  version; deprecation = re-pin elsewhere; published packs are never deleted
  (snapshots are already immutable). Pin changes are audited (RULE_PACK_CHANGE).
- D58 Q: Authoring UI? → Deferred to saro-screen-review (D7); guide doc + API
  path only.

## STORY-375 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path / finding |
|---|---|---|
| Version surface | ⚠️ hardcoded | `main.py:274` FastAPI(version="8.0.0"); `/health` returns `app.version`; **no single source, no /api/v1/version** |
| CHANGELOG | ❌ absent | changelog-drafter workflow exists (propose-only, drafts from Conventional Commits) but **no CHANGELOG.md** and no CI entry gate |
| Deploy pipeline | ✅ partial | `deploy.yml` on main push → flyctl deploy + `/health` schema_ok check; **no tag-triggered release pipeline** |
| Conformance suite (AC-3 dep) | ✅ | `tests/test_story361_conformance.py` (df606a7) |
| Canary (AC-3 dep) | ✅ | `.github/workflows/canary.yml` (52da248), `workflow_run` on Deploy |

## Decision Log — STORY-375 (appended)
- D51 Q: Version single source? → `_version.py::__version__`, imported by main.py
  (FastAPI version + health) and a new `/api/v1/version` endpoint. One string,
  one place; a test asserts main.py does not re-hardcode it.
- D52 Q: CHANGELOG format + gate? → Keep-a-Changelog. CI gate fails a
  release-labelled PR whose diff does not add a CHANGELOG entry — the drafter
  proposes, the gate enforces that a human curated one before release.
- D53 Q: Release pipeline shape? → tag `v*` → conformance + full pytest → deploy
  → post-deploy canary (reuse existing jobs; do NOT duplicate deploy logic).
- D54 Q: Rollback rehearsal? → documented; the actual rehearsal on a scratch
  deploy is **[HUMAN — OPEN]** (needs Fly access), like the DR rehearsal.

## STORY-374 — premise check (PLAN stage 3a) — DELTA on STORY-MTR-001
| Referenced artifact | Verified? | Path / finding |
|---|---|---|
| Metering machinery | ✅ EXTENSIVE | `services/metering_service.py` (MTR-001): meter keys, idempotency, statements, thresholds, `reconcile()` |
| PHI-free by construction (AC-5) | ✅ already done | closed `DIMENSION_KEYS` + 64-char value cap — MTR-001 built AC-5 |
| Authoritative attestation table | ✅ | `models.ScanReport` (one row per audit; `tenant_id`, `created_at`) |
| Attest boundary (AC-1) | ⚠️ **gap** | `services/audit_submission.submit_audit_sync` writes ScanReport but does NOT meter — only `rule_pack_versions.py` increments today |
| Recount invariant (AC-2) | ⚠️ **partial** | `reconcile()` uses a **tolerance** + covers one key vs GRCEvidenceRecord; pack wants **0% exact** + a CLI |
| CSV/JSON export (AC-3) | ❌ | statement endpoint returns JSON via API; no CSV, no CLI export |

## Decision Log — STORY-374 (appended)
- D47 Q: Rebuild metering? → **No — delta only.** MTR-001 already gives PHI-free
  meters, idempotency, and immutable statements. This story wires the
  evaluate/attest boundary, adds an EXACT recount, adds export + CLI.
- D48 Q: Boundary increment semantics? → `safe_increment` (fail-open) keyed by
  `audit_id` idempotency, in `submit_audit_sync`. One ScanReport = one
  attestation, deduped by audit id, so the meter recounts EXACTLY against the
  table. A metering fault must never block an evaluation or lose an attestation.
- D49 Q: reconcile()'s tolerance vs the pack's "within 0%"? → Add a distinct
  `verify_exact` requiring an **exact** match against the authoritative table;
  leave `reconcile()` (drift-tolerance data-quality alerting) as-is. They answer
  different questions — do not overload one.
- D50 Q: Payment processor? → **Out of scope, stated in the doc.** Export only;
  Stripe is a later story. Metering is evidence-grade, billing is not built.

## STORY-373 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| Operator CLI to extend | ✅ | `cli.py` — click group, `CliError`, `_session_factory()`, existing `ingest`/`demo` commands |
| Idempotency precedent + its hazard | ✅ | `scripts/seed_demo_tenant.py::ensure_demo_user` + **FND-058** (silently reassigned tenant/role on an email match — must not repeat) |
| Adapter/log-source placeholder | ✅ | `models.TenantLogSourceConfig` (migration 037, one row per tenant, `enabled` defaults false) |
| Admin audit write (AC-4) | ✅ | `services/self_audit.record_privileged`, `ADMIN_ACTION` |
| BAA gate artifacts (INV-6) | ✅ | `compliance/baa/STORY-BAA-01/02` |
| Isolation probe helpers (AC-2) | ⚠️ partial | `tests/test_story365_route_authz.py` is route-level; tenant-row isolation lives in `tests/test_pt009_tenant_isolation_concurrency.py` — the CLI check is written fresh against the DB rather than importing test helpers into product code |

## Decision Log — STORY-373 (appended)
- D43 Q: Idempotency semantics for a re-run? → **Never mutate an existing
  tenant.** Re-running reports what already exists and exits 0. FND-058 is the
  cautionary case: matching on a weak key and silently reassigning
  tenant/role/password. Provisioning must be safe to re-run *because operators
  re-run it when unsure*, and "safe" means inert, not "re-applies defaults".
- D44 Q: Admin password? → **Generated, printed once, never stored or logged.**
  No default, no fallback (FND-044 class). If the operator loses it they
  re-issue rather than recover it.
- D45 Q: BAA gate enforcement? → CLI **refuses** without `--baa-confirmed`,
  naming the artifact. INV-6 is a hard gate; a doc-only step gets skipped under
  time pressure, which is precisely when it matters.
- D46 Q: Isolation check — import the test helpers? → No. Product code must not
  import from `tests/`. The check is written against the DB directly and asserts
  the new tenant reads zero rows of another tenant's data.

## STORY-372 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| Canary (AC dependency) | ✅ | `.github/workflows/canary.yml` (52da248) |
| `/health` contract | ✅ | `main.py::health` — `status`, `db_ok`, `version` |
| Somewhere to serve a static page | ✅ | Vite `publicDir` default → `frontend/public/` copied to `dist`, served by `frontend/nginx.conf` |
| SLA doc to link from | ✅ | `docs/legal/sla-draft-v0.1.md` §4 |

## Decision Log — STORY-372 (appended)
- D39 Q: Canary writes a status file, or the page probes live? → **Probe live.**
  A cached "all systems operational" banner is worse than no status page: during
  an outage it states the opposite of the truth, which is exactly when someone
  reads it. Live probing cannot go stale.
- D40 Q: Independence? → The page is served by the frontend app, so it **shares
  that app's fate** — a real limitation, stated on the page itself rather than
  hidden. True independence needs third-party hosting = a human signup decision.
- D41 Q: Treat HTTP 503 from `/health` as down? → **Degraded.** 503 is the
  documented healthy-process/unhealthy-dependency response; calling it a hard
  outage would misreport a partially working system.
- D42 Q: On fetch error, show anything optimistic? → Never claim health that
  could not be confirmed — unreachable renders red, DB renders "unknown".

## FND-065 — authentication events (red-first)
Premise check: `routers/self_audit.py` already exposes
`GET /api/v1/audit/events` with `actor` + `action_class` filters, so the *query*
half of "reconstruct a session history" exists — only emission was missing.
Confirmed no logout endpoint exists (FND-002, open), so logout is out of scope.

- D35 Q: Fail closed (like `record_privileged`) or open (like `record_access`)
  on the login path? → **Open.** Fail-closed means a self-audit DB problem locks
  everyone out *including the operator trying to diagnose it* — an audit gap
  becomes a total outage, and you cannot log in to fix the thing causing it.
  Matches the documented tradeoff already in `services/self_audit.py`
  ("compliance-function availability beats self-audit completeness"). The gap is
  made visible by an ERROR log rather than silence.
- D36 Q: Record failed logins? → **Yes, and they are the more valuable half** —
  brute force and credential-stuffing are invisible without them. Unknown emails
  have no tenant, so those land on `SYSTEM_TENANT_ID`.
- D37 Q: Source IP in the event? → Include. It is envelope metadata, not message
  content, and an auth trail without origin cannot answer "who used this". Note:
  personal data under GDPR (security legitimate interest), **not** PHI — no
  patient information can reach this path (INV-2 holds).
- D38 Q: Actor for a failed unknown-email attempt? → Record the **submitted**
  email. It is the only identifying handle, and withholding it defeats the
  purpose; it is already attacker-supplied, so no new exposure.

## FND-066 — token revocation (red-first, after STORY-370)
Premise check: `auth.py` `create_access_token` emits sub/email/role/persona/
tenant/exp only; `get_current_user` validates signature + expiry + is_active.
No `jti`, no `token_version`, no denylist — confirmed, so the finding is real.

Red first: 6 of 9 tests failed before the fix (version claim absent, stale token
accepted, forged higher version accepted, legacy token trusted, no revoke helper).

- D31 Q: `jti` denylist or monotonic `token_version`? → **token_version.** A
  denylist needs storage that grows with every revocation and must be consulted
  on every request; a version integer is one column, compared against a claim
  already being decoded, and revokes ALL of a user's sessions at once — which is
  what credential rotation actually needs.
- D32 Q: Tokens without the claim (issued before this ships)? → **Reject them.**
  Treating a missing claim as "matches" leaves the exact hole this finding
  describes open for the lifetime of every already-issued token. Fails closed;
  cost is that everyone re-logs in once at deploy, which is the correct price.
- D33 Q: Mismatch direction? → Reject on **any** difference, not just older. A
  token claiming a *higher* version than the row is forged or replayed.
- D34 Q: Commit inside the helper? → No. Caller owns the transaction so
  revocation lands atomically with the password change that prompted it.

## STORY-370 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path |
|---|---|---|
| Existing chain verifiers to reuse | ✅ **eight of them** | `services/self_audit.py`, `rule_pack_snapshot_service.py`, `evf_publication_service.py`, `disposition_service.py`, `observation_coverage_service.py`, `audit_emitter.py`, `hash_chain_service.py`, `grc/evidence.py` |
| Immutable rule-pack snapshots | ✅ | `models.RulePackSnapshot` (content/prev/record hash), RPV-001 |
| A7 backup-failure alert placeholder | ✅ | `docs/ops/alerts.md` A7 — says "placeholder until STORY-370" |
| Supabase backup settings | ❌ cannot verify from repo | provider console — documented as a **config-to-confirm checklist**, not asserted |

## Decision Log — STORY-370 (appended)
- D27 Q: Post-restore verification = run the existing chain verifiers? →
  **Insufficient, and dangerously so.** Every existing verifier proves a chain
  is *internally self-consistent*; a **truncated** chain is still
  self-consistent. Restoring a backup missing the last N events returns
  `valid: true` from all eight while evidence is silently gone. Verification
  therefore needs a **reference manifest captured before the loss**
  (tip hash + record count per chain), stored off-platform with the backup.
- D28 Q: Compare tip hash alone? → No. Count *and* tip, because they fail
  differently: equal count + different tip = **TAMPER**; lower count =
  **DATA_LOSS** (and the delta is the measured RPO); higher count = **AHEAD**,
  meaning verification ran after traffic resumed — a procedural error worth
  naming rather than silently passing.
- D29 Q: Testability with no live DB? → Split pure comparison logic from thin DB
  adapters. The logic worth testing (truncation/tamper/loss classification) is
  pure and unit-tested against fixture manifests; adapters just wrap the
  existing verifiers.
- D30 Q: RTO/RPO numbers? → **Left blank.** They are *measured* by the rehearsal
  (AC-4, human-gated, scratch project only). Writing plausible numbers before
  rehearsing would be exactly the claimed-without-evidence failure (FM-1).

## STORY-371 — premise check + my own FM-2 violation
| Referenced artifact | Verified? | Finding |
|---|---|---|
| `docs/ops/support-model.md` | ❌ absent | created by this story |
| IRP v1.0 contested claims | ✅ present | FND-064 — reconciled here as v1.1 |
| `GET /api/v1/governance/ir-plan` hardcodes `sla_hours: 1` | ✅ | `routers/governance.py:77` — must move with the doc |
| Token revocation on password change | ❌ **does not exist** | no `jti`, no `token_version`, no denylist in `auth.py`/`models.py` → FND-066 |
| Anything emitting `AUTH_EVENT` | ❌ **nothing does** | the class is in `self_audit.py`'s vocabulary; **no code path emits it** → FND-065 |

**My own unverified premise (CLAUDE.md FM-2).** In STORY-366 I justified
classifying `POST /api/v1/auth/token` as DATA_PLANE with "login — auth events
handled by the auth path". I did not check. Nothing records logins. The
justification asserted a mechanism that does not exist, and it is precisely why
the tabletop could not answer "was the leaked credential used?". Corrected in
`services/admin_audit_registry.py` with the truth and a finding reference.
The premise-check discipline works only when applied to my own claims too.

## STORY-368 — premise check (PLAN stage 3a)
| Referenced artifact | Verified? | Path / finding |
|---|---|---|
| `/health` endpoint | ✅ | `main.py::health` — returns `ok/degraded/schema_mismatch`, 503 when unhealthy, `db_ok` |
| `/metrics` endpoint | ❌ **does not exist** | route dump confirms absent — this story creates it |
| `prometheus_client` dependency | ❌ **not in requirements.txt** | `middleware/rate_limiter.py` imports it *optionally* with a pure-python fallback → the metrics layer must not hard-depend on it |
| Ingestion watermark source | ✅ | `models.ObservationCheckpoint.watermark_timestamp` (COV-001/002) |
| Free cron slots | ✅ | taken: Mon 02:00/03:00/04:17, daily 05:23/06:00, Sun 02:00 |

## Decision Log — STORY-368 (appended)
- D23 Q: Expose `/metrics` publicly (normal for Prometheus) or authenticate? →
  **Bearer token (`METRICS_TOKEN`), 401 without — fail closed.** Even
  count-only metrics reveal traffic shape and deployment health to anyone; a
  public endpoint is also a free liveness oracle for an attacker. Unset token
  means no valid credential exists, so every request 401s (never "open when
  unconfigured", the CORS anti-pattern already flagged in main.py).
- D24 Q: Per-tenant metric labels? → **Never.** A tenant label set leaks the
  customer list and per-customer volumes to any scraper — an INV-3 disclosure
  through the side door. Metrics are global aggregates only; per-tenant volume
  lives in metering (STORY-374) behind normal authz. Pinned by test.
- D25 Q: Depend on prometheus_client? → No — hand-rolled exposition. It is not
  a declared dependency and adding one for a text format that is ~40 lines
  would put a scrape path at the mercy of an optional import.
- D26 Q: Ingestion-lag threshold N? → **90 minutes**, configurable. Assumes an
  hourly mirror-async pull: 90 min tolerates one missed cycle plus grace but
  catches two consecutive misses. Assumption stated in the doc — if the pull
  cadence changes, the threshold must move with it.

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
