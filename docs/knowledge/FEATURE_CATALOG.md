# SARO Feature Catalog

Zero-hallucination inventory of every feature area in the SARO backend
(`routers/*.py`, `main.py`) and frontend (`frontend/src/pages/*.jsx`). Grouped
by function, not by file, so it reads as a product catalog. Every endpoint
list is exhaustive for the router(s) named — nothing is summarized away.

Convention: `role` = the coarse `users.role` column (`super_admin`/`operator`,
plus the synthetic `demo_viewer`). `persona` = the fine-grained
`users.persona_role` column (`compliance_lead`/`risk_officer`/`ai_auditor`/`admin`).
See [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) for how these interact.

---

## 1. Risk Scanning — the core product

**What it does:** SARO accepts a `prompt` + `raw_output` (or a batch of them)
that some *other* system produced, and scores it for risk. SARO never
generates the output it audits and never calls an external model to do the
scoring itself (one narrow, disclosed exception — see §7).

Two ingestion shapes exist:

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST /api/v1/scan` | `routers/scan.py:255-377` | Batch scan: ≥50 samples, runs the full 4-gate pipeline (`engine.run_audit`) |
| `POST /api/v1/scan/data` | `routers/scan.py:451-563` | Same pipeline, accepts the `saro-data-framework`'s batch shape (fairness-labeled samples: gender/ethnicity/ground_truth) |
| `POST /api/v1/audit/output` | `routers/output_audit.py:163-289` | Single-output audit: one prompt+output pair, runs Gates 3+4 only (`engine.run_output_audit`) |
| `POST /api/v1/ingest` | `routers/ingest.py:201-272` | Async version of single-output audit — returns 201 immediately, runs the engine in a background task |
| `POST /api/v1/hf/process` | `routers/hf_processor.py:175-228` | Batch-processes queued rows from `hf_sample_queue` (populated by the external `saro-data-framework` tool) through the same single-output engine path |

**Auth:** all five require `role in (super_admin, operator)`.

**What actually happens inside the engine** (`engine.py`, `SARoEngine.run_audit`,
`engine.py:1082-1184`) — see [DOCS_VS_CODE_GAPS.md](DOCS_VS_CODE_GAPS.md) for
where this differs from what CLAUDE.md describes:

1. **Gate 1 — Data Quality** (`engine.py:1329-1391`): hard-fails if fewer than
   50 samples (`MIN_SAMPLES`, an internal statistical heuristic, not a
   regulatory requirement — see `docs/COMPLIANCE_CLAIMS_MATRIX.md`). Only gate
   that can hard-block the whole audit.
2. **Gate 2 — Fairness** (`engine.py:1395-1472`): Statistical Parity
   Difference across a `group` label; warns/fails at 10%/20% gap.
3. **Gate 3 — Risk Classification** (`engine.py:1498-1707`): keyword/regex
   scan against per-domain signal patterns (`_RISK_SIGNALS`), optionally
   confirmed/pruned by an LLM judge (§7a).
4. **Prompt-injection scan** (`engine.py:1943-2065`): evidence-only, runs
   after Gate 3, never affects the score (§8).
5. **Gate 4 — Compliance Mapping** (`engine.py:1739-1805`): maps triggered
   domains to rule-pack obligations; never fails, only scores 0–1.
6. **Bayesian scoring** (`engine.py:2356-2418`): a Beta-Binomial posterior
   mean per domain and overall — this is the number persisted as
   `overall_risk_score`. **Not** the "DIR" formula documented in CLAUDE.md.
7. MIT coverage score, incident-similarity matching (TF-IDF against the
   `ai_incidents` corpus), fixed-delta computation, remediation suggestions.

**Result storage:** `Audit` + `ScanReport` (+ `AuditMetadata` for single-output)
rows, plus a hash-chained `AuditTrace` row per check (§3).

---

## 2. Prompt-Injection Detection

**What it does:** a fully deterministic, regex-based scanner — separate from
the risk-scoring gates — that looks for prompt-injection patterns in the
audited text. **Evidence-only**: findings never change the Bayesian risk score
or fail/warn a gate.

- Detector: `rule_packs/injection/detector.py` — normalizes text (strips
  zero-width chars, folds Cyrillic/Greek homoglyphs to Latin, NFKC-normalizes),
  bounded base64/ROT13 decoding of embedded payloads (decode-bomb guarded),
  then matches an 8-rule, versioned, SHA-256-hashed corpus
  (`rule_packs/injection/1.0.0/pack.yaml`) mapped to MITRE ATLAS technique IDs.
- Findings are PII-redacted before being written to TRACE (`engine.py:1991`).
- **Optional LLM-assisted second pass** for samples the deterministic detector
  did *not* flag (§7b) — held-out generalization check, still evidence-only.

---

## 3. TRACE — Audit Trail & Evidence Export

**What it does:** every gate check, domain flag, injection finding, and rule
application becomes one `AuditTrace` row, hash-chained (SHA-256, `event_hash`/
`prev_hash`) for tamper-evidence. This is SARO's core "evidence, not
certification" mechanism (see `docs/COMPLIANCE_CLAIMS_MATRIX.md`).

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/traces/{audit_id}` | `routers/traces.py:40-68` | All trace rows for an audit |
| `GET /api/v1/traces/{audit_id}/failed` | `routers/traces.py:71-103` | Only fail/warn/flagged rows |
| `GET /api/v1/traces/{audit_id}/summary` | `routers/traces.py:106-150` | Aggregated per-gate counts |
| `GET /api/v1/traces/{audit_id}/samples` | `routers/traces.py:153-182` | Per-sample Gate-3 findings |
| `POST /api/v1/traces/{audit_id}/{trace_id}/remediate` | `routers/traces.py:237-276` | Marks one trace remediated |
| `GET /api/v1/audit/{audit_id}/trace` | `routers/trace_view.py:117-177` | Human-readable 6-step TRACE timeline + integrity verdict |
| `GET /api/v1/audit/{audit_id}/trace/export` | `routers/trace_view.py:180-240` | Signed JSON export (HMAC-SHA256) + RFC 3161 timestamp |
| `GET /api/v1/audit/{audit_id}/export/{json,pdf}` | `routers/trace_view.py:243-374` | Signed JSON/PDF evidence pack |
| `POST /api/v1/trace/{audit_id}/export` | `routers/trace_export.py:186-216` | A second, distinctly-keyed signed export (own HMAC secret, own PDF renderer via `fpdf2`) |
| `POST /api/v1/trace/{audit_id}/verify` | `routers/trace_export.py:254-275` | Verifies a caller-supplied export hash |
| `GET /api/v1/audit/verify-chain` | `routers/audit_chain.py:80-157` | Recomputes the full hash chain for an audit and reports integrity status |
| `GET /api/v1/dashboard/audits/{audit_id}/trace` | `routers/dashboard.py:341-444` | Chain-of-thought + executive summary (lazily synthesized, cached on `EnhancedTrace`) |
| `GET /api/v1/audit/output/{audit_id}` | `routers/output_audit.py:298-318` | Full `EnhancedTrace` (verbatim prompt/output + export hash) for single-output audits |

**Note:** there are **two independent, differently-keyed signed-export
mechanisms** (`trace_export.py` and `trace_view.py`) producing overlapping but
not identical JSON/PDF evidence packs — worth reconciling if this is
confusing downstream.

**Auth:** mostly `role in (super_admin, operator)`; the persona-aware reads
(`trace_view.py`, `dispositions.py`-adjacent) additionally admit
`ai_auditor`/`compliance_lead` personas via `TRACE_READ_ROLES`/`TRACE_READ_PERSONAS`.

---

## 4. Dashboard, Risk Register & Board Reporting

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/dashboard/kpis` | `routers/dashboard.py:188-269` | Tenant KPIs (audit counts, avg risk/MIT, pending remediations, 30-day trend) |
| `GET /api/v1/dashboard/audits` | `routers/dashboard.py:275-335` | Audit list with computed `risk_color` (green/yellow/red) |
| `GET /api/v1/risks` / `{risk_id}` | `routers/risks.py:95-137` | Risk register — maps completed audits to risk-register rows |
| `PATCH/DELETE /api/v1/risks/{risk_id}`, `POST /api/v1/risks/bulk` | `routers/risks.py:140-228` | Owner/status edits, soft-delete, bulk actions — writes to `risk_metadata` |
| `GET /api/v1/risk/summary` | `routers/risk_dashboard.py:107-115` | Board-level aggregated risk summary |
| `GET /api/v1/risk/vendors`, `/vendor-risk` | `routers/risk_dashboard.py:118-128,646-653` | Risk breakdown by AI vendor/model — **flagged as likely buggy**, see below |
| `GET /api/v1/risk/whats-changed` | `routers/risk_dashboard.py:131-171` | 7-day risk-score delta |
| `GET /api/v1/risk/board-export`, `/risk-dashboard/board-summary(.pdf)` | `routers/risk_dashboard.py:174-643` | Board-ready PDF/JSON with RAG status, HMAC verification hash |
| `GET /api/v1/compliance_matrix`, `/risk_dashboard`, `/dashboard` | `routers/fe_dashboard.py:47-231` | A **second**, differently-named set of dashboard endpoints (underscore paths) — see caveat below |

**Known bug:** `routers/risk_dashboard.py:99-100` reads
`report.risk_score`/`report.confidence` via `getattr(...)`, but `ScanReport`'s
real columns are `overall_risk_score`/`confidence_score` (confirmed in
`models.py:176-179` and used correctly elsewhere, e.g. `trace_view.py:282-283`).
This means `/api/v1/risk/vendors` and `/api/v1/risk/whats-changed` are very
likely always computing against `None`. Worth a targeted fix.

**Naming collision to be aware of:** `fe_dashboard.py`'s `/api/v1/risk_dashboard`
(underscore) is a *different module* from `risk_dashboard.py`'s `/api/v1/risk/*`
and `/api/v1/risk-dashboard/*` (hyphen) — they produce related but distinct
data under confusingly similar paths.

---

## 5. Compliance Hub & Framework Evidence

**What it does:** presents NIST AI RMF, EU AI Act, ISO 42001, and AIGP
"evidence support" — never a compliance certification (see
`docs/COMPLIANCE_CLAIMS_MATRIX.md` for the exact allowed/forbidden language).

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/compliance/hub` | `routers/compliance_hub.py:136-171` | Recent audits + internal RAG claims status + readiness checklist — **currently broken, see ROLES doc** |
| `GET /api/v1/compliance/dpa` | `routers/compliance_hub.py:174-228` | Generates/streams a GDPR Art. 28 DPA PDF |
| `GET/PUT /api/v1/compliance/readiness` | `routers/readiness.py:41-66` | Tenant readiness checklist (manual + derived items) |
| `GET /api/v1/compliance-matrix/*` | `routers/compliance_matrix.py:119-302` | Global (not tenant-scoped) framework coverage %, CSV export |
| `GET /api/v1/reports/nist-coverage` | `routers/reports.py:344-404` | Coverage status for 68 NIST AI RMF 1.0 subcategories, mechanically derived from `engine._COMPLIANCE_TRIGGERS` |
| `POST /api/v1/reports/{audit_id}/iso42001-annex` | `routers/reports.py:501-607` | Generates a versioned, hash-locked ISO 42001 Annex document with `[AUTO]`/`[HUMAN REVIEW REQUIRED]` sections |
| `GET /api/v1/aims/documents/{doc_id}/evidence-pack` | `routers/aims.py:223-287` | ISO 42001 Clause 9 evidence pack aggregating linked audits |
| `GET /api/v1/evf/validation-status*` | `routers/evf_sprint3.py:45-72` | Tier 1/2/3 external-validation status per framework — currently all **Tier 3 (not assessed)**, see `docs/COMPLIANCE_CLAIMS_MATRIX.md` EVF section |
| `GET /api/v1/governance/*` | `routers/governance_trust.py`, `routers/governance.py` | Static trust-center documents (SOC 2 roadmap, NIST self-assessment, DPA template, IR plan) |

---

## 6. Rule Packs, Versioning & Drift Alerts

**What it does:** the compliance-citation content (which obligations each
risk domain maps to) is versioned, hash-chained data, not hardcoded logic.

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/rules/packs`, `/packs/{framework}` | `routers/rule_packs.py:23-43` | List/read rule packs |
| `GET /api/v1/rules/drift-alerts` | `routers/rule_packs.py:71-77` | **Framework-version drift** — compares active pack versions to a hardcoded "latest known" map. This is the *only* real "drift" feature — see [DOCS_VS_CODE_GAPS.md](DOCS_VS_CODE_GAPS.md) for why this is not the KS-test/statistical drift CLAUDE.md describes |
| `POST/GET /api/v1/rules/versions*` | `routers/rule_pack_versions.py:60-187` | Freezes working rule tables into an immutable, hash-chained snapshot (`rule_pack_snapshots`); diff/verify/reproduce a pinned version |
| `GET /api/v1/evidence/{evidence_id}/criteria` | `routers/evidence_criteria.py:30-80` | Reproduces the exact rule-pack content an evidence record was pinned to |

Five rule-pack **schemas** exist under `rule_packs/` (compliance-citation
packs, envelope allowlist, MITRE ATLAS registry, injection detector, and
observation packs) — see [DOCS_VS_CODE_GAPS.md](DOCS_VS_CODE_GAPS.md) for the
two orphaned legacy files (`rule_packs/eu_ai_act_v1.0.yaml`,
`rule_packs/nist_rmf_v1.0.yaml`) that use an incompatible schema and are
never loaded by any code path.

---

## 7. Optional External Model Usage (Gate-3 LLM Judge)

Per `docs/COMPLIANCE_CLAIMS_MATRIX.md`'s "External Model Usage" section, this
is the *one* disclosed exception to "SARO never calls external models," and
it's off unless a tenant sets `ANTHROPIC_API_KEY`.

- **(a) MIT-domain confirmation** (`engine.py:1710-1735`): re-checks
  keyword-flagged samples and can *drop* (never add) a flag — false-positive
  reduction only.
- **(b) Semantic injection judge** (`engine.py:2067-2131`): assesses samples
  the deterministic injection detector did *not* flag, for held-out
  generalization — evidence-only, cannot affect the score.

Both default to `claude-sonnet-4-20250514` via `SARO_LLM_JUDGE_MODEL`,
capped at `MAX_LLM_CALLS_PER_BATCH=200` calls each, PII-redacted before
egress.

---

## 8. Remediation & Finding Disposition

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/remediation`, `/audits/{id}/traces`, `/{id}/progress` | `routers/remediation.py:322-611` | Open-findings queue, per-audit remediation progress |
| `PATCH /api/v1/remediation/traces/{trace_id}/remediate` | `routers/remediation.py:170-236` | Marks a finding remediated |
| `POST /api/v1/remediation/bulk-remediate` | `routers/remediation.py:621-698` | Bulk remediation |
| `POST /api/v1/remediation/traces/{trace_id}/create-jira-issue` | `routers/remediation.py:241-319` | Creates a Jira Cloud issue from a finding (requires tenant Jira OAuth, see below) |
| `GET /api/v1/remediation/oauth/jira/{start,callback}` | `routers/remediation.py:416-529` | Jira Cloud OAuth2 3LO flow, HMAC-signed replay-guarded state |
| `GET/POST/PATCH /api/v1/dispositions/*` | `routers/dispositions.py:69-207` | Formal finding lifecycle: acknowledge → remediate/escalate/waive (with required justification/approver/expiry) → auto-reopen on waiver expiry |

**Known dead code:** `POST /api/v1/coverage/systems` (`routers/remediation.py:718-730`)
returns a stub success with no DB write. `GET /api/v1/coverage`
(`routers/remediation.py:733-747`) always operates on a hardcoded empty list
and therefore always reports zero systems — this looks unfinished, not
functional.

---

## 9. AI Insights (Automated Remediation Recommendations)

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/insights` | `routers/insights.py:149-184` | Derives insights **read-only, at request time** from existing audit/trace/risk data — explicitly no external model call on this path |
| `POST /api/v1/insights/{insight_id}/action` | `routers/insights.py:187-297` | Records accept/snooze/dismiss; `ai_auditor` persona is denied write (read-only by design) |

---

## 10. AI System / Model Inventory — three overlapping registries

**Important for documentation clarity:** there are **three separate,
non-unified** "inventory" mechanisms in the codebase. Anyone relearning the
product should understand these are distinct:

1. **`ai_systems` / `system_audits`** (`routers/systems.py`) — EU AI Act
   Art. 49-style inventory. `eu_ai_act_risk_tier` is a human-decision-only
   field; an in-code comment explicitly forbids the engine from setting it
   automatically. Currently **empty** (0 rows) — no frontend page calls its
   endpoints (confirmed: not in the frontend page list).
2. **`aims_documents`** (`routers/aims.py`) — "AIMS" (AI Management System)
   document lifecycle, the one actually wired to the frontend
   (`Aims.jsx` → "Model Inventory" page). ISO 42001 Clause 9 evidence.
3. **`grc_registry_entries`** (`routers/grc_registry.py`) — GRC Epic 1 asset
   registry with EU AI Act/NIST tiering fields and its own immutable audit
   trail (`grc_registry_audit`). No frontend page found calling it.

If the goal is one unified "AI system inventory" feature, this is the
concrete gap: three parallel data models exist, only one has a UI.

---

## 11. GitHub Integration (Read-Only Code Scanning)

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST /api/v1/github/configure` | `routers/github_integration.py:199-268` | Validates a GitHub PAT, stores only its SHA-256 hash; blocked for EU-region tenants pending a DPA amendment |
| `GET /api/v1/github/status`, `DELETE /disconnect` | `routers/github_integration.py:277-309` | Status / disconnect |
| `POST /api/v1/github/scan-with-token/{audit_id}` | `routers/github_integration.py:371-473` | Searches configured repos for MIT-domain keywords via GitHub's search + contents API; stores only ≤500-char snippets + hash, never full files |
| `POST /api/v1/github/scan/{audit_id}` | `routers/github_integration.py:318-362` | **Always returns 501** — kept only to redirect callers to the `-with-token` variant |

Zero rows in `github_integrations`/`github_scan_results` — nobody has
configured a PAT yet. Feature is fully implemented, just unused.

---

## 12. Offline Evaluation Framework

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST /api/v1/evaluations/trigger` | `routers/evaluations.py:167-210` | Runs SARO's own scan pipeline against 5 fixed public datasets (RealToxicityPrompts, Guardrails Hallucination, PII Masking, CrowS-Pairs, TruthfulQA) via the external `saro_data` package |
| `GET /api/v1/evaluations`, `/latest`, `/{run_id}` | `routers/evaluations.py:219-278` | Evaluation run history |
| `POST /api/v1/evaluations/ingest` | `routers/evaluations.py:306-347` | Ingests a `run_report.json` posted by a scheduled GitHub Actions CI job |

This is `saro-data-framework/` from CLAUDE.md's architecture diagram —
confirmed as a standalone package, not imported by `engine.py`, that
downloads/converts public datasets into SARO's batch JSON shape.

---

## 13. Observation Coverage (Log-Ingestion Cadence Monitoring)

**What it does:** attests that SARO is actually receiving a client's AI
system logs on schedule — a distinct concern from risk *content* scoring.

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST /api/v1/observation-coverage/checkpoint` | `routers/observation_coverage.py:39-58` | Adapter reports a watermark position (regex-constrained opaque token, never free text) |
| `POST /api/v1/observation-coverage/detect-gaps` | `routers/observation_coverage.py:61-68` | Sweeps for missed cadence windows, opens `observation_gaps` rows |
| `GET /api/v1/observation-coverage/gaps`, `/report` | `routers/observation_coverage.py:71-117` | Gap list / coverage % + max lag report |

`observation_checkpoints` (76 rows) and `observation_gaps` (5 rows) are
populated — this feature is actively used. `observation_lag_samples` (0 rows)
is not — see [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for the likely reason
(a separate p50/p95 aggregation job that isn't running).

---

## 14. Usage Metering

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/metering/usage` | `routers/metering.py:34-46` | Current-period usage totals |
| `POST /api/v1/metering/statement` | `routers/metering.py:49-67` | Issues an immutable, content-hashed usage statement |
| `GET /api/v1/metering/reconcile` | `routers/metering.py:70-80` | Reconciles meters vs. authoritative counts |

`usage_meters`/`usage_statements`/`usage_meter_idempotency` are all empty —
worth checking whether the scan/ingest pipelines actually call the meter
*increment* path anywhere (not confirmed by this audit — the routers that run
audits, `scan.py`/`ingest.py`, were not observed calling a metering-increment
function).

---

## 15. Notifications

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/notifications`, `/unread-count` | `routers/notifications.py:45-84` | List / unread count |
| `PATCH /{id}/read`, `POST /read-all` | `routers/notifications.py:87-127` | Mark read |
| `GET /api/v1/notifications/stream` | `routers/notifications.py:133-177` | Server-Sent-Events real-time stream |

`scan.py:61-115` dispatches a notification when `overall_risk_score` crosses
0.60/0.80 thresholds. The `notifications` table is currently empty despite
170 audits existing — worth checking directly whether any audit actually
crossed those thresholds, since this could be either expected (all scores
below threshold) or a silent failure in the dispatch path.

---

## 16. Enterprise Client Onboarding (SSO / SCIM / MFA)

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST /api/v1/clients` | `routers/clients.py:112-239` | Full tenant onboarding: SSO/SCIM/MFA config, initial users, one-time SCIM token |
| `POST /{tenant_id}/test-sso` | `routers/clients.py:355-429` | Live-validates SSO config against the IdP |
| `POST /{tenant_id}/scim/rotate-token` | `routers/clients.py:432-461` | Rotates the SCIM bearer token |
| `GET/PUT /clients/security-contact` | `routers/clients.py:281-336` | 72-hour breach-notification contact (FND-067) |
| SAML SSO: `GET /sso/metadata/{slug}`, `/sso/login/{slug}`, `POST /sso/acs/{slug}` | `routers/sso.py` | Full SP-initiated SAML flow with signature verification, replay-guard, JIT provisioning, MFA enforcement |

---

## 17. EVF — External SME Validation Framework (QCO Registry)

**What it does:** tracks the *business process* of getting a framework claim
externally validated by a qualified SME firm, culminating in a Qualified
Compliance Opinion (QCO) reference. This is the mechanism behind
`docs/COMPLIANCE_CLAIMS_MATRIX.md`'s EVF section.

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST/GET /api/v1/evf/engagements*` | `routers/evf.py` | SME engagement lifecycle + 7-item validation gate |
| `POST/GET/PATCH /api/v1/evf/qco*` | `routers/evf_sprint2.py` | QCO draft → publish → renew, hash-chained publication events |
| `GET /api/v1/evf/validation-status*`, `/qco/expiry-alerts` | `routers/evf_sprint3.py` | Tier 1/2/3 status per framework, expiry monitoring |

All EVF tables are currently empty — **expected**, not a bug: per
`docs/COMPLIANCE_CLAIMS_MATRIX.md`, no framework has entered SME validation
yet ("Internal Review Only" for all four frameworks as of 2026-06-02). The
feature is fully implemented, waiting for a real SME engagement to be entered.

---

## 18. Self-Audit (SARO's Own Immutable Action Log)

Distinct from the customer-facing `AuditTrace`/TRACE system — this is SARO
auditing *itself*.

| Endpoint | File:line | Purpose |
|---|---|---|
| `GET /api/v1/audit/events` | `routers/self_audit.py:54-101` | Queries SARO's privileged-action log (tenant or system scope) |
| `GET /api/v1/audit/events/verify` | `routers/self_audit.py:104-115` | Verifies the self-audit hash chain |
| `GET /api/v1/audit-events` | `routers/clients.py:467-488` | A second, `super_admin`-only immutable event log (`AuditEvent` model) |

---

## 19. Auth, Tenancy & Demo Mode

| Endpoint | File:line | Purpose |
|---|---|---|
| `POST /api/v1/auth/bootstrap` | `routers/auth.py:44-91` | One-time first-tenant/first-admin creation (409 after first use) |
| `POST /api/v1/auth/token`, `GET /me` | `routers/auth.py:149-271` | Login, current-user profile |
| `POST /api/v1/auth/register` | `routers/auth.py:218-252` | Create a user (super_admin only) |
| `PATCH /api/v1/auth/users/{id}/persona` | `routers/auth.py:360-394` | Set a user's persona — see ROLES doc for the allowlist |
| `POST/GET /api/v1/tenants` | `routers/auth.py:279-328` | Tenant provisioning/listing |
| `POST /api/v1/demo/signup` | `routers/demo.py:42-102` | Public demo-request form (off by default, `DEMO_REQUESTS_ENABLED` flag) |
| `GET /api/v1/demo/token` | `routers/demo.py:164-229` | Issues a 4-hour, read-only `demo_viewer` JWT bound to a fixed demo tenant |

---

## 20. Miscellaneous

- **Feedback** (`routers/feedback.py`): in-product feedback submission +
  internal triage queue.
- **Engine status** (`routers/engine_status.py`): health/version/rule-pack-hash
  of the running engine singleton.
- **Version** (`routers/version.py`): public, unauthenticated build-info endpoint.
- **Metrics** (`routers/metrics_endpoint.py`): Prometheus scrape endpoint,
  token-gated, fails closed if `METRICS_TOKEN` is unset.
- **Governance stubs**: `POST /api/v1/governance/erasure-request` and
  `/retention-policy` (`routers/governance.py:29-60`) return response-only
  stubs with **no visible DB persistence** in the router itself — flagged,
  not confirmed as broken (may persist via a service module not covered here).

---

## Frontend — what's actually built

The frontend is **fully migrated to React/Vite** — Streamlit was removed
(`STORY-105`, confirmed: no Streamlit files exist, only a stale vendor
`node_modules` artifact). ~30 pages under `frontend/src/pages/`, every one
with a co-located Vitest test file. Full page-by-page endpoint mapping is in
the frontend agent's inventory (available on request) — the notable
structural facts are:

- Navigation is a **client-side page switcher** (`AppShell.jsx`), not
  React-Router routes — persona determines which tabs are visible via a
  `PERSONA_TABS` allowlist in `Sidebar.jsx`.
- `Settings.jsx` and `AdminSettings.jsx` are **two different, overlapping**
  settings surfaces — see [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md)
  for why `Settings.jsx` is the one with the disconnected role vocabulary.
- Demo mode enforces its own tab whitelist (`demoTabs.json`) independently of
  the persona system, and deliberately never touches `localStorage` for the
  demo token.
