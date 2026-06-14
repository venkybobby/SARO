# SARO Gap Remediation Stories — Marcus Hale Pressure Test v1.0

Source: Buyer-Critic Pressure Test §4 Gap Analysis Table (June 2026)
Numbering: STORY-001–012 in gap-table order. Cross-refs to existing SARO backlog IDs preserved.

-----

## STORY-001: External SME Validation Chain & QCO Registry Execution

Status: draft | Cross-ref: EVF P-0→P-3, FR-EVF-01–22
Screen/Area: Governance / EVF Program (process + product)

**Goal**
Close the 20/25 risk-register vulnerability: obtain Qualified Credentialed Opinions (QCOs) from named external SMEs for at least the NIST AI RMF and EU AI Act rule-pack scopes, and persist them in a populated, queryable QCO Registry so “who validated this?” has a verifiable answer.

**Acceptance Criteria**

- AC-1: Given the EVF SME register is empty, When P-1 sourcing completes, Then ≥2 credentialed external SMEs (NIST AI RMF, EU AI Act) are contracted with verifiable references stored in the registry.
- AC-2: Given an SME completes a rule-pack review, When the QCO is issued, Then the QCO record (SME identity, credentials, scope, date, findings, signature hash) is stored in the QCO Registry and retrievable via API/UI.
- AC-3: Given a compliance claim is rendered in any report or the Claims Matrix, When the claim’s framework scope has no issued QCO, Then the claim displays an “UNVALIDATED — internal review only” marker (FR-EVF gating).
- AC-4: Given a buyer requests validation evidence, When the evidence package is exported, Then it includes the QCO documents and reference-check attestations per EVF §2.3.

**Edge Cases**

- SME issues a qualified/partial QCO (scope carve-outs) — claim gating must honor the carve-out, not the whole framework.
- SME credential lapses or QCO expires — registry must support expiry dates and auto-revert claims to UNVALIDATED.
- Rule pack changes after QCO issuance — QCO is pinned to a rule-pack hash (depends on STORY-008); a new hash invalidates the QCO.

**Out of Scope**

- ISO 42001 and AIGP QCOs (deferred per 90-day plan).
- Automated SME workflow tooling beyond registry CRUD.

**Non-Functional Requirements**
QCO records immutable once issued (append-only, hash-chained like AUD-001); registry reads <500ms; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-002: Sample-Level Evidence Persistence with PII Redaction

Status: draft | Cross-ref: SARO-001 (P0)
Screen/Area: Audit Engine / Evidence Chain

**Goal**
Stop discarding `_SampleFlag` in memory. Persist sample-level and signal-level detection evidence (sample ID, matched rule, matched keyword/pattern, redacted text fragment) so an auditor can reproduce any finding down to the specific outputs that triggered it.

**Acceptance Criteria**

- AC-1: Given a Gate 4 run produces detections, When the run completes, Then every triggered signal is persisted with sample ID, rule ID, matched pattern, and a redacted text fragment.
- AC-2: Given an auditor opens a finding, When they request “show triggering samples,” Then the UI/API returns the exact N samples and matched fragments that produced the finding.
- AC-3: Given a sample contains PII, When the fragment is persisted, Then PII is redacted before write (never stored raw) and redaction is covered by a passing test.
- AC-4: Given a historical report, When its findings are re-queried, Then sample-level evidence is retrievable for the report’s retention window.

**Edge Cases**

- Very large runs (>100k samples) — persistence must be batched; no blocking writes in async context (per March audit fix pattern).
- Fragment itself is entirely PII — store rule + sample ID with fragment = “[REDACTED-FULL]”.
- Duplicate samples triggering the same rule — dedupe at signal level but preserve count.

**Out of Scope**

- Full raw-sample storage; only redacted fragments.
- Retroactive backfill of pre-release runs.

**Non-Functional Requirements**
No raw PII at rest (DPA dependency); Postgres staging-table pattern (no Redis); write overhead <10% of current run time; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-003: Framework Citation Correction & Citation Verification Pass

Status: draft | Cross-ref: SARO-002 (P0)
Screen/Area: Rule Packs / Framework Citations

**Goal**
Fix the verified citation error (50-sample minimum misattributed to EU AI Act Art. 10 / NIST MAP 2.3) and run a one-time verification pass over all framework citations so a single wrong citation cannot collapse credibility of the set.

**Acceptance Criteria**

- AC-1: Given the 50-sample-minimum rule, When its citation renders anywhere (UI, reports, exports), Then it no longer cites EU AI Act Art. 10 / NIST MAP 2.3 and instead cites the correct internal-methodology source.
- AC-2: Given the full citation inventory, When the verification pass completes, Then every citation is checked against source text and the result (verified/corrected/removed) is logged in a citations audit file committed to the repo.
- AC-3: Given a future rule pack adds a citation, When CI runs, Then a citations lint check requires an entry in the citation inventory.

**Edge Cases**

- Citations to framework sections that were renumbered in later framework versions — pin framework version in the citation.
- Citations that are “inspired by” rather than literal — must be labeled “informed by,” never “per.”

**Out of Scope**

- Re-mapping NIST coverage (STORY-007).

**Non-Functional Requirements**
Standard project rules; citation inventory is a versioned repo artifact (ISO 42001 Cl. 7.5 alignment).

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-004: SOC 2 Type I Readiness & Engagement

Status: draft | Cross-ref: Deal Condition #4 (process track)
Screen/Area: Vendor Security / Compliance Operations

**Goal**
Pass enterprise vendor-risk intake: complete SOC 2 Type I readiness, sign an engagement letter with an auditor, and commit Type II within 12 months.

**Acceptance Criteria**

- AC-1: Given the Trust Services Criteria (Security baseline), When readiness assessment completes, Then a gap list with owners and dates exists in the doc register (STORY-005).
- AC-2: Given control gaps, When remediation completes, Then evidence (access reviews, change management, logging, IR plan) is collected in an evidence repository mapped to TSC.
- AC-3: Given readiness, When the auditor is selected, Then a signed Type I engagement letter exists and is shareable under NDA with prospects.

**Edge Cases**

- Solo-founder segregation-of-duties findings — document compensating controls explicitly rather than hiding the constraint.
- Fly.io shared-responsibility boundaries — inherit provider attestations where valid, document the split.

**Out of Scope**

- SOC 2 Type II execution (committed, not delivered, this cycle).
- Pen test (tracked under STORY-009 conditions / Deal Condition #5).

**Non-Functional Requirements**
Process track — no code NFRs; evidence repository access-controlled and versioned.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-005: Canonical Document Register & Claims Reconciliation

Status: draft | Cross-ref: FR-EVF-17 retrospective audit; ISO 42001 Cl. 7.5
Screen/Area: Documentation / Document Control

**Goal**
Eliminate same-month contradictions (IR/DPA status, Neon vs Supabase, Railway vs Fly.io) by establishing a single source-of-truth document register with versioning, and reconciling all live documents against it.

**Acceptance Criteria**

- AC-1: Given the current document set, When reconciliation completes, Then exactly one canonical status exists for each gap (IR plan, DPA, SME validation) and superseded documents are marked SUPERSEDED with a pointer to the canonical version.
- AC-2: Given the infrastructure of record, When any document references the stack, Then it matches the single canonical architecture doc (Fly.io + Supabase + Postgres staging) or fails review.
- AC-3: Given the FR-EVF-17 retrospective claims audit, When run against the current sales/demo deck, Then every claim is tagged verified / corrected / withdrawn with the result logged.

**Edge Cases**

- Documents embedded in third-party locations (PDFs already shared externally) — issue errata, don’t silently revise.
- Conversation-only commitments (two-tier RTO) — either document them formally or formally retract them; no orphan claims.

**Out of Scope**

- Building an in-product document-lifecycle feature (that’s SARO product scope, not internal doc control).

**Non-Functional Requirements**
Register lives in the SARO repo (integrated delivery rule); every doc carries version, date, owner, status header.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-006: ISO 42001 Annex Documentation Generator

Status: draft | Cross-ref: SARO-005
Screen/Area: Reports / ISO 42001 Module

**Goal**
Generate ISO 42001 Annex technical documentation drafts from existing platform data (runs, drift, findings, remediation), with explicit [AUTO] / [HUMAN REVIEW REQUIRED] markers, validated by an ISO 42001 lead auditor QCO — addressing the heaviest AIMS evidence workload.

**Acceptance Criteria**

- AC-1: Given a tenant with audit history, When the generator runs, Then it produces Annex-mapped documentation sections with each paragraph tagged [AUTO] or [HUMAN REVIEW REQUIRED].
- AC-2: Given the generated document, When exported, Then it carries the signed export hash (TRC-002/CF-01 pattern) and engine/rule-pack provenance (STORY-008).
- AC-3: Given an ISO 42001 lead auditor review, When the QCO is issued for the generator’s output mapping, Then the QCO is registered per STORY-001 before the feature exits beta.
- AC-4: Given Annex clauses SARO does not cover, When the document renders, Then those clauses appear with an explicit “NOT COVERED BY SARO — manual evidence required” section (Supports/Does Not Replace discipline).

**Edge Cases**

- Tenant with insufficient run history — generator must refuse with a minimum-evidence message, not emit thin documents.
- Mixed-framework tenants — ISO output must not import unvalidated NIST/EU claims.

**Out of Scope**

- Clause 9/10 management-review and internal-audit support (explicitly “Does Not Replace”).
- Full 13/13 Annex A coverage claims.

**Non-Functional Requirements**
Generation <60s for standard tenant; output deterministic for identical input (auditability); standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-007: Honest NIST AI RMF Coverage Report Endpoint

Status: draft | Cross-ref: SARO-004
Screen/Area: API + Reports / Coverage Map

**Goal**
Publish a code-verified NIST AI RMF coverage map (currently 8/72 subcategories) as an API endpoint and report section, so coverage claims are mechanically derived from `_COMPLIANCE_TRIGGERS` rather than asserted — converting the overclaim risk into a trust asset and the contract claims baseline (Deal Condition #7).

**Acceptance Criteria**

- AC-1: Given the current rule packs, When GET /coverage/nist-rmf is called, Then the response lists all 72 subcategories with status covered / partial / not-covered, derived from code, not a static file.
- AC-2: Given a rule pack change in CI, When triggers are added/removed, Then the coverage map updates automatically and a snapshot diff is logged.
- AC-3: Given any report claiming NIST alignment, When rendered, Then it embeds the coverage map version and count (e.g., “8 of 72 subcategories, map vX”) — no unqualified “NIST AI RMF aligned” strings anywhere in product or export.

**Edge Cases**

- A trigger mapping to multiple subcategories — count each mapping once per subcategory, no double-claiming.
- Partial coverage definitions — require a documented rubric for “partial” before any subcategory uses it.

**Out of Scope**

- Expanding actual coverage beyond 8 (separate roadmap epics).

**Non-Functional Requirements**
Endpoint read-only, tenant-agnostic, cached; map regeneration runs in CI; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-008: Engine Version & Rule-Pack Hash Provenance on Reports

Status: draft | Cross-ref: SARO-006
Screen/Area: Audit Engine / Report Export

**Goal**
Stamp every report and export with engine version and rule-pack content hash, and compute `export_hash` over raw engine output plus provenance — so historical evidence is attributable to the exact configuration that produced it.

**Acceptance Criteria**

- AC-1: Given any audit run, When it executes, Then engine semver and SHA256 of the active rule-pack set are recorded on the run record.
- AC-2: Given a report export, When the export hash is computed, Then it covers raw engine output + provenance fields, not only the synthesized trace, and tamper tests (AUD-001 pattern) pass.
- AC-3: Given a historical report, When an auditor queries it, Then the exact engine version and rule-pack hash render on the report and are independently verifiable against the repo’s tagged releases.

**Edge Cases**

- Rule pack hot-fixed mid-day — two runs same day must show different hashes.
- Reports generated before this story — render “PROVENANCE UNAVAILABLE (pre-vX)” honestly rather than backfilled values.

**Out of Scope**

- Re-signing historical exports.

**Non-Functional Requirements**
Hash computation adds <1s per export; provenance fields immutable post-write; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-009: Persona RBAC Enforcement & Multi-Tenant Isolation Test Suite

Status: draft | Cross-ref: Epic 9 (PER-001–004), SEC-002, PERF-004
Screen/Area: Auth / RBAC + Tenant Isolation

**Goal**
Move RACI from documents into the product: enforce backend RBAC for the three buyer personas (Compliance Lead, Risk Officer, AI Auditor) and prove tenant isolation under concurrent load.

**Acceptance Criteria**

- AC-1: Given a user with the AI Auditor role, When they call a write/remediation endpoint, Then the backend returns 403 (enforcement server-side, not UI-hidden).
- AC-2: Given the persona→tab mapping from v3, When each persona logs in, Then only mapped tabs/endpoints are accessible, verified by automated tests per persona.
- AC-3: Given two tenants with concurrent runs, When the isolation suite executes (≥50 concurrent sessions), Then zero cross-tenant reads/writes occur, asserted at the query layer.
- AC-4: Given the legacy personas (Forecaster/Autopsier/Enabler/Evangelist), When the release ships, Then they are removed or explicitly mapped — no unenforced orphan roles remain in code.

**Edge Cases**

- User with multiple roles — permissions are union, audited per-action with the effective role logged.
- `/demo` read-only auto-auth route — must map to a locked demo role; verify it cannot escalate.
- JWT role claims tampered — signature validation rejects (no hardcoded secret regression from March audit).

**Out of Scope**

- Customer-defined custom roles.
- SSO/SCIM provisioning.

**Non-Functional Requirements**
Every authz denial logged with tenant, user, role, endpoint; isolation suite runs in CI nightly; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-010: Tenant-Configurable Risk Weights with Documented Defaults

Status: draft | Cross-ref: SARO-003
Screen/Area: Risk Engine / Tenant Configuration

**Goal**
Replace hardcoded domain weights (Privacy 0.85, Socioeconomic 0.50, etc.) with tenant-level configuration over documented defaults, and publish the derivation methodology so scoring survives audit-committee questioning.

**Acceptance Criteria**

- AC-1: Given default weights, When any report renders a risk score, Then the weights used and a link/reference to the “How SARO Reasons” methodology doc are embedded in the report.
- AC-2: Given a tenant admin (Risk Officer role per STORY-009), When they adjust a weight within allowed bounds, Then subsequent runs use tenant weights and the change is written to the hash-chained audit log.
- AC-3: Given the confidence formula and the 0.80 cap, When the methodology doc is published, Then both are documented with rationale, and the cap is either justified or made configurable with bounds.

**Edge Cases**

- Weight changed mid-quarter — historical scores must not retro-change; runs pin the weight set used (provenance pattern, STORY-008).
- Tenant sets degenerate weights (all 0 or all 1) — validation bounds reject with explanation.

**Out of Scope**

- Per-business-unit sub-tenant weights (post-pilot).
- Replacing the Bayesian core / Jeffreys prior (tracked separately).

**Non-Functional Requirements**
Weight reads cached per run; config changes effective next run, never mid-run; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-011: Incident Corpus Quality Dashboard & Similarity Floor

Status: draft | Cross-ref: SARO-007
Screen/Area: Risk Engine / Incident Similarity

**Goal**
Stop presenting noise as signal: enforce a minimum cosine-similarity threshold for incident matches and expose corpus size, currency, and composition on a quality dashboard.

**Acceptance Criteria**

- AC-1: Given an incident-similarity match below the configured floor (default proposed: 0.30, confirm with data), When results render, Then the match is suppressed from reports (optionally visible in a debug view).
- AC-2: Given the corpus, When the dashboard loads, Then it shows record count, date range, last-refresh date, and source breakdown.
- AC-3: Given a report that includes similarity matches, When rendered, Then each match shows its similarity score and the active floor — a 0.85 and a 0.31 are never visually equivalent.

**Edge Cases**

- Empty or stale corpus (>12 months since refresh) — reports must show a corpus-staleness warning instead of silently matching.
- Floor change — pinned per run (STORY-008 pattern) so historical reports remain explainable.

**Out of Scope**

- Corpus expansion/sourcing program (separate initiative).

**Non-Functional Requirements**
Dashboard query <2s; floor configurable per tenant within bounds; standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|

-----

## STORY-012: Vendor Continuity Package — Escrow, Infrastructure Freeze, Key-Person Mitigation

Status: draft | Cross-ref: Deal Condition #6 (process track)
Screen/Area: Vendor Operations / Business Continuity

**Goal**
Neutralize the solo-founder/viability objection: complete and freeze the Fly.io migration, establish source-code escrow, and document a continuity/hiring plan suitable for an MSA exhibit.

**Acceptance Criteria**

- AC-1: Given the Fly.io migration, When this story closes, Then backend and frontend run on Fly.io with `auto_stop_machines=false`, the health-check timeout on `saro-backend` is resolved, and Railway/Koyeb references are removed from canonical docs (per STORY-005).
- AC-2: Given an escrow provider, When the agreement executes, Then the SARO repo deposits on a defined cadence with verified release conditions, referenceable in the MSA.
- AC-3: Given the continuity plan, When documented, Then it names backup operational coverage (deploy, restore, IR execution) and a hiring sequence, versioned in the doc register.

**Edge Cases**

- Escrow release-condition disputes — conditions must be objective (e.g., 30-day unremediated outage), not discretionary.
- Infra emergency requiring a provider change despite the freeze — requires a documented exception with customer notice, not a silent migration.

**Out of Scope**

- Actual hiring execution.
- Multi-region active-active deployment.

**Non-Functional Requirements**
Process track; infra-as-config committed to repo (fly.toml canonical); standard project rules.

**Traceability (filled at close by /story)**

|AC|Test(s)|Files|
|--|-------|-----|