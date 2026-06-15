# SARO — Implementation Gap Analysis (Code-Verified)

> **Date:** 2026-06-15 · **Method:** Direct source verification against the live codebase
> (`venkybobby/SARO`), not planning docs or prior summaries.
> **Inputs reviewed:** `SARO_ClaudeCode_DevPlan_v1_0.docx` (Phase 10, 17 stories),
> `SARO_Screen_Interrogation_Prompt.md.pdf` (React frontend audit, 26 screens / 16 stories),
> `saro_live_gap_analysis.html` (prior LIVE-001…008 analysis).
> **Headline:** The codebase is materially **ahead** of all three planning docs. ~80% of specced
> functionality is BUILT and tested. The remaining work is concentrated in **evidence/metrics
> artifacts** (not product code) plus **one real citation-leak bug** and a few frontend finishes.

---

## 1. Phase 10 backend stories (DevPlan v1.0)

| Story | Title | Verdict | Evidence / Gap |
|---|---|---|---|
| Epic 9 | Persona RBAC enforcement | ✅ BUILT | `services/persona_service.py` `persona_required()`; JWT carries `persona_role` (`auth.py:133`); migration 004 seeds 4 personas. Enforcement wired but **narrow** — only `compliance_hub` router decorates with it. |
| S-1001 | EVF Artifact Pack | 🟡 PARTIAL | Present: COI form, SOW template, language-tier policy, QCO template (`docs/evf/`). **Missing 3 of 6:** `sme-qualification-criteria`, `claims-challenge-protocol`, `evf-retention-addendum`. Test `test_sar004_evf.py` does **not** assert file existence. |
| S-1002 | Doc Register + Claims Audit | ✅ BUILT | `docs/DOCUMENT_REGISTER.md` (canonical), `docs/evf/evf_retrospective_audit_2026-06-02.json`, `docs/CLAIMS_AUDIT_LOG.md`; `test_pt005_doc_register.py`. |
| S-1003 | QCO Registry + Badges | ✅ BUILT | `QCORegistry` + `QCOPublicationEvent` models; migrations 011–013, 022; `routers/evf_sprint2.py`/`evf_sprint3.py` (CRUD + publish + hash-chain); `compliance_label_service.py`. **Minor gap:** prohibited-words check ran once as an audit JSON; **no active CI lint** preventing regressions. |
| S-1004 | SME Evidence Packages | 🟡 PARTIAL | SME state machine + 7-item ValidationGate built. **Missing:** `docs/evf/evidence-package-nist/` and `-euaiact/` content (largely founder/SME calendar-bound, external to code). |
| S-1101 | Sample-Level Finding Persistence | ✅ BUILT | `SampleFinding` model + Gate-3 bulk insert with `_redact_pii()`; `GET /traces/{id}/samples` tenant-scoped. **Minor:** no composite index on `(audit_id, domain)` despite spec. |
| S-1102 | Engine / Rule-Pack Provenance | ✅ BUILT | `engine_version` + `rule_pack_hash` (SHA-256 of signals+triggers) + `compliance_matrix_version` on `ScanReport`; `GET /reports/engine-integrity`; `test_pt008_provenance_export.py`. |
| S-1103 | Scoring Methodology + FP Baseline | 🟡 PARTIAL | Methodology documented in `docs/how-saro-reasons.md` (formula, weights, 0.80 cap, Bayesian). **Missing the entire FP-baseline half:** `tests/fixtures/fp_baseline/` (100+ labeled/domain), `tests/test_fp_baseline.py`, `docs/metrics/detection-baseline.md`, the >5pp CI regression gate. |
| S-1104 | Citation Accuracy Fix (Gate G-4) | 🔴 GAP | Fixed in `engine.py` + `docs/CITATION_INVENTORY.md`, **but `routers/scan.py:232` and `:407` still read `"Minimum 50 samples required (EU AI Act Art. 10, NIST MAP 2.3)"`.** The lint `test_pt003_citations.py:34` only scans `engine.py`, so it stays green — the AC "repo-wide grep: zero Art. 10 in minimum-sample contexts" is **not met**. See §4. |
| S-1105 | Honest NIST Coverage | ✅ BUILT | `GET /reports/nist-coverage` mechanically derived from `_COMPLIANCE_TRIGGERS`; statuses validated by `test_pt007_nist_coverage.py`. NB: map holds **68** subcategories (honestly labelled), not 72 — verify the denominator is the intended one. |
| S-1106 | Incident Corpus Transparency | 🟡 PARTIAL | Stats endpoint, 0.15 similarity floor, `low_confidence` flag all built (`test_pt011_incident_floor.py`). **Gap:** AC required `fixed_by`/`fixed_at` audit columns on `ai_incidents`; only the `is_fixed` boolean exists. |
| S-1107 | Tenant Isolation Evidence | 🟡 PARTIAL | Isolation proven at 50 concurrent tenants (`test_pt009_tenant_isolation_concurrency.py`). **Missing the evidence-pack deliverables:** `scripts/generate_security_evidence.py`, signed PDF in `docs/evidence/`, weekly CI schedule, Trust-page download link. |
| S-1201 | Fly.io Freeze + Architecture | ✅ BUILT | `fly.toml` `auto_stop_machines='off'`; `docs/ARCHITECTURE.md` CANONICAL; `/health` smoke. |
| S-1202 | Trust Page — IR Plan + RTO | ✅ BUILT | `docs/incident-response-plan.md`; `GET /governance/ir-plan` with RTO/SLA table; `routers/governance_trust.py`. Confirm Claims-Matrix "Gap 1 → CLOSED" wording is set. |
| S-1203 | DPA + Retention Publication | ✅ BUILT | `docs/legal/saro-dpa-template-v1.0.md`, `docs/sample-evidence-retention.md`, trust-page endpoints; `test_sar009_dpa.py`. Confirm "Gap 3 → CLOSED" wording. |
| S-1204 | SOC 2 Readiness | ✅ BUILT | `docs/soc2-readiness-roadmap-v1.0.md` (TSC mapping + status rows + "no attestation yet"); surfaced via `/governance/docs/soc2-roadmap`. |
| S-1205 | Niche Demo + Pilot Collateral | 🟡 PARTIAL | Demo data already vendor-output-audit shaped (`demo_data/*.json`). **Missing:** `docs/pilot-one-pager.md` (1 BU / max 25 models) and the documented demo-script repositioning + FR-EVF-16 language audit record. |

**Backend score:** 11 BUILT · 6 PARTIAL · 1 GAP (of 18 incl. Epic 9).

---

## 2. Frontend screen audit (Screen Interrogation PDF)

The PDF was written against an **older** frontend. Most of its bugs/stories are already resolved
(STORY-111/112/113/114/016 landed). Verified against `frontend/src`:

| Audit claim | Current status | Evidence |
|---|---|---|
| 6 personas defined | ✅ TRUE | `Sidebar.jsx` ROLE_LABELS; `AdminSettings.jsx` PERSONAS |
| Phantom tab `evidence_export` (=TraceView) | ✅ FIXED | removed (STORY-111) |
| Phantom tab `vendor_risk` (=RiskSummary) | ✅ FIXED | merged into Risk Register (STORY-113) |
| Phantom tab `ir_plan` (=GovernanceDocs) | ✅ FIXED | consolidated into Trust Center (STORY-112) |
| BUG-001: no persona switch UI | ✅ FIXED | avatar dropdown in `Sidebar.jsx` (admin/super_admin) |
| STORY-001: admin user mgmt needs raw UUID | ✅ FIXED | `AdminSettings.jsx` user list + search + per-row persona dropdown |
| RiskRegister mock data (`MOCK_RISKS`) | ✅ FIXED | fetches `/api/v1/risks` |
| AIInsights mock data (`MOCK_INSIGHTS`) | ✅ FIXED | `insightsService.js` → `/api/v1/insights` |
| STORY-003: scan→TRACE link | ✅ FIXED | "View TRACE" button in `Upload.jsx` |
| STORY-005: Knowledge Portal | ✅ FIXED | `KnowledgePortal.jsx` + `TrustCenter.jsx` |
| STORY-004: Risk create form | ✅ FIXED | `RiskForm.jsx` (create + edit) |
| STORY-016: Demo Requests removed | ✅ FIXED | de-listed from nav (orphan `.jsx` remains — dead code) |
| STORY-012/014: Reports charts | 🟡 PARTIAL | `Reports.jsx` charts are **placeholders**; export buttons are no-ops ("Connect a charting library…") |

**Frontend gaps:** Reports charts/export not wired; orphaned `DemoRequests.jsx` to delete.

---

## 3. Prior HTML analysis (LIVE-001…008) — re-verified

Every LIVE item from `saro_live_gap_analysis.html` is now **resolved** in code:

| Item | Then | Now |
|---|---|---|
| LIVE-001 persona_role in JWT | missing | ✅ `auth.py:133` |
| LIVE-002 hashed_password NOT NULL | bug | ✅ nullable (`models.py:69`, migration 017); SSO sets `None` |
| LIVE-003 CORS wildcard+creds | unsafe | ✅ gated on `ALLOWED_ORIGINS`; `*`⇒`allow_credentials=False` |
| LIVE-004 GitHub EU/GDPR gating | none | ✅ `_require_non_eu_tenant` 403 (migration 019 `data_region`) |
| LIVE-005 token expiry/refresh | 60-min only | 🟡 per-tenant `token_expire_minutes` (migration 018); **no `/auth/refresh`** |
| LIVE-006 demo request alert | silent | ✅ Slack webhook via BackgroundTask (`sales_notification_service.py`) |
| LIVE-008 SSO ACS validation | unverified | ✅ signature + `NotOnOrAfter` + replay guard (`routers/sso.py`) |
| (SPEC-E1) LLM hybrid classifier | absent | ✅ optional, off-by-default Gate-3 judge gated on `ANTHROPIC_API_KEY` |
| Auth rate limiting | weak | 🟡 auth endpoints **allowlisted/exempt** from limiter — no brute-force/enumeration cap |

---

## 4. The one real correctness bug — S-1104 citation leak

`routers/scan.py`:
```python
# line 232 (scan_batch)  and  line 407 (scan_data_batch)
"**Minimum 50 samples required** (EU AI Act Art. 10, NIST MAP 2.3)."
```
This is the exact misattribution S-1104 was created to remove (the 50-sample floor is an internal
heuristic, per `COMPLIANCE_CLAIMS_MATRIX.md` "Sampling Methodology Basis"). It survives in
user-facing 422 error bodies. The pinning test is blind to it because
`test_pt003_citations.py::test_sample_floor_not_attributed_to_regulation_in_engine` reads **only
`engine.py`**. Gate G-4 therefore reports green on an unmet AC.

**Fix (small, high-credibility):**
1. Replace both strings with internal-methodology language, e.g.
   `"Minimum 50 samples required (internal SARO statistical methodology — see Sampling Methodology Basis)."`
2. Broaden `scripts/check_citations.py` to scan `routers/` and `schemas.py`, not just `engine.py`,
   so the lint actually enforces the repo-wide AC. Then re-grep to confirm zero matches.

---

## 5. Prioritized gap backlog (what's left to build)

**P0 — correctness / gate integrity**
- [ ] Fix S-1104 citation leak in `routers/scan.py:232,407` + widen the citation lint scope. (§4)

**P1 — evidence & metrics deliverables (claims defensibility)**
- [ ] S-1103 FP baseline: `tests/fixtures/fp_baseline/` (100+ labeled/domain), `test_fp_baseline.py`,
      `docs/metrics/detection-baseline.md`, >5pp CI regression gate.
- [ ] S-1107 security evidence: `scripts/generate_security_evidence.py` → signed PDF in
      `docs/evidence/`; weekly CI schedule; Trust-page link.
- [ ] S-1106 audit columns: add `fixed_by`/`fixed_at` to `ai_incidents` + write-on-change.
- [ ] S-1003 add an **active** prohibited-words lint test to CI (not just the one-off audit JSON).

**P1 — auth hardening**
- [ ] Per-endpoint brute-force / enumeration rate limit on `/auth/token` + magic-link (currently exempt).
- [ ] (Optional) `/auth/refresh` endpoint — today only per-tenant expiry exists.

**P2 — documentation artifacts**
- [ ] S-1001: author the 3 missing EVF docs + assert their existence in `test_evf_docs`.
- [ ] S-1205: `docs/pilot-one-pager.md` (1 BU / 25 models) + documented demo-script repositioning.
- [ ] S-1004: compile NIST + EU AI Act evidence-package folders (founder/SME-bound).

**P2 — frontend finish**
- [ ] `Reports.jsx`: wire a real charting lib + implement PDF/CSV export.
- [ ] Delete orphaned `frontend/src/pages/DemoRequests.jsx` (dead code).

**Verify (non-code confirmations)**
- [ ] Confirm Claims-Matrix "Gap 1 / Gap 3 → CLOSED" wording is actually set (S-1202/S-1203).
- [ ] Confirm intended NIST denominator (68 mapped vs the 72-subcategory framing).
- [ ] Broaden Epic 9 `persona_required` decoration beyond `compliance_hub` if persona-gating is
      meant to be enforced server-side on more routers (frontend tab-filtering ≠ API enforcement).
