# SARO — Purpose, Core Problem & Current Gaps

Grounded in `docs/pilot-one-pager.md` (the team's own decided positioning,
FB-033/FB-044/S-1205), `docs/COMPLIANCE_CLAIMS_MATRIX.md`, `CLAUDE.md`'s
non-negotiables, and the code-level audit in
[FEATURE_CATALOG.md](FEATURE_CATALOG.md) / [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) /
[DOCS_VS_CODE_GAPS.md](DOCS_VS_CODE_GAPS.md). Where a claim comes from an
existing doc rather than code, that's stated explicitly.

---

## The core problem SARO solves

Stated directly in `docs/pilot-one-pager.md:8-13` (this is the team's own
framing, not my paraphrase):

> Mid-market regulated firms increasingly buy AI-powered tools from vendors
> (chat assistants, underwriting models, clinical summarisers). They are
> accountable for those outputs but have **no independent, evidence-based way
> to audit them** — vendor self-attestations are not enough for an internal
> risk function or an external examiner.

In plain terms: a compliance/risk team at a regulated company (insurance,
healthcare, finance) is on the hook for what an AI vendor's tool produces, but
has no systematic way to check those outputs for risk, and no evidence trail
to show an examiner beyond "the vendor said it's fine." SARO exists to fill
that gap **from the buyer's side, not the vendor's** — it's an independent
auditor of AI output, not a tool for AI builders to certify their own models.

## What SARO actually is, mechanically

A human (a **Compliance Lead**, per the pilot's lead persona) feeds SARO a
`prompt` + `raw_output` pair — something a vendor's AI already produced. SARO:

1. Runs a deterministic 4-gate pipeline (Data Quality → Fairness → Risk
   Classification → Compliance Mapping) and computes a Bayesian risk
   probability — **verified in code**, see [FEATURE_CATALOG.md §1](FEATURE_CATALOG.md).
2. Writes a hash-chained, tamper-evident evidence trail (TRACE) for every
   check performed.
3. Maps triggered risk domains to specific obligations in NIST AI RMF, EU AI
   Act, ISO 42001, and AIGP — **evidence support, never a certification**
   (`docs/COMPLIANCE_CLAIMS_MATRIX.md`).
4. Surfaces remediation guidance and a disposition workflow so a human can
   act on what's flagged.

The six non-negotiables in `CLAUDE.md` (never calls external models to
produce the audited output, returns only score+TRACE+guidance, never writes
to client systems, never self-certifies compliance, always human-in-the-loop,
read-only integration posture) are the product's actual thesis: **SARO's
value is that it is not another black-box AI system you have to trust — it's
a deterministic, evidence-generating check on the AI systems you already
don't trust enough.** That's also why the one disclosed exception (the
optional Gate-3 LLM judge) is off by default and evidence-only — even SARO's
own use of AI is designed to never become something requiring blind trust.

## Who it's for, right now

Per the pilot scope (`docs/pilot-one-pager.md:27-34`): one business unit, up
to 25 vendor AI tools, led by a Compliance Lead with Risk Officer/AI Auditor
support, 6–8 weeks. This is a **narrow, deliberately bounded pilot** for
mid-market regulated buyers auditing *third-party* vendor output — not yet an
org-wide platform, not a pre-deployment model-lifecycle tool, and not (yet) a
tool the vendors themselves would use to certify their own models.

---

## Gaps — what SARO is not solving right now

Organized by what kind of gap each one is, since "not built yet," "built but
broken," and "built but incoherent" call for different responses.

### 1. The compliance-evidence value prop is currently self-graded

Per `docs/COMPLIANCE_CLAIMS_MATRIX.md`'s EVF section, **no framework has
completed External SME Validation** — all four (NIST, EU AI Act, ISO 42001,
AIGP) sit at "Internal Review Only — Not for External Claim." The entire
EVF/QCO machinery to fix this is built (`routers/evf*.py`) but has zero rows
in production — nobody has started an SME engagement yet. Until that
happens, the evidence SARO produces is graded by SARO's own rule packs, not
independently validated — which is exactly the "vendor self-attestation isn't
enough" problem the product exists to solve, just one level up. This is a
business-process gap, not a code gap, but it's the single biggest thing
standing between "evidence support" and a credible external compliance claim.

### 2. The role/persona system that's supposed to run this doesn't fully work

The pilot's whole model depends on a Compliance Lead being able to review
evidence, with Risk Officer/AI Auditor support. In practice:
- `GET /api/v1/compliance/hub` — the Compliance Lead's home screen — currently
  **denies every persona**, including `compliance_lead` itself, due to an
  argument-unpacking bug in `auth.py`'s `persona_required()`
  (`routers/compliance_hub.py:138`).
- Persona enforcement is narrow by design — of 47 router files, only this one
  decorates with `persona_required` at all (confirmed by direct grep) — most
  other routers rely on the coarser `role` check or the broader
  `require_role_or_persona`. This was already flagged in the prior
  (2026-06-15) gap analysis as "narrow"; it's still narrow today, and the one
  place it is used doesn't work.
- Two of the role names actually in use at your org — "Implementation Lead"
  and "Risk Auditor ISO 42001" — have no representation anywhere in the
  system, and the frontend has a second, disconnected role vocabulary
  (`Settings.jsx`) that doesn't match the real one. Full detail in
  [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md).

### 3. No real drift/monitoring over time — the "Orchestrator" half of the name is thin

The only implemented "drift" detection is rule-pack **version** staleness
(is a framework's rule pack out of date), not statistical drift on a vendor's
actual output distribution over time. CLAUDE.md and `.claude/skills/drift-sentinel/SKILL.md`
describe a KS-test/2σ statistical-drift feature with circuit breakers and
PagerDuty routing — none of it exists in code (verified, zero hits for every
named symbol). If part of the pitch to a buyer is "SARO watches for a
vendor's risk profile degrading over time," that capability needs to be built
from scratch — it's a documented aspiration, not a shipped feature.

### 4. Per-feature explainability (SHAP) is also not implemented

Explainability today is a plain-language summary of the top-3 risk domains by
Bayesian probability — useful, but not the per-feature attribution SHAP would
provide and that the risk-scoring skill file describes. If a buyer's
examiner asks "which specific words/phrases drove this score," SARO's answer
today is a domain-level summary, not a token-level one.

### 5. Board/vendor risk reporting is likely silently broken

`routers/risk_dashboard.py:99-100` reads `report.risk_score`/`report.confidence`
via `getattr(...)`, but the real `ScanReport` columns are
`overall_risk_score`/`confidence_score`. `GET /api/v1/risk/vendors` and
`/api/v1/risk/whats-changed` — exactly the views a Risk Officer would use to
tell a board "which vendor is our riskiest" — are very likely always
computing against `None`. This directly undermines the "Risk Officer support"
half of the pilot's staffing model.

### 6. Alerting on high-risk findings is unconfirmed

`scan.py` is supposed to dispatch a notification whenever a score crosses
0.60/0.80. With 170 audits on record and zero notifications, either every
single audit has scored low (possible, not verified) or the alerting path is
silently failing. Either way, "SARO proactively flags high-risk vendor output"
— a reasonable buyer expectation for something with "Orchestrator" in the
name — is not currently demonstrable from the data.

### 7. Three parallel, non-unified "which AI systems do we even audit" registries

`ai_systems`, `aims_documents`, and `grc_registry_entries` are three separate
data models for the same underlying question (what AI systems/vendor tools
are in scope), only one of which (`aims_documents`) has a frontend page. A
buyer with 25 vendor tools in scope (the pilot's own stated ceiling) has no
single place in the product to see them all — this is a foundational gap for
a product whose pitch depends on covering "up to 25" vendor tools coherently.

### 8. Usage metering isn't wired into the path that would need it

No evidence was found of the scan/ingest pipelines calling a metering
increment function, despite 170 audits existing. If usage-based billing,
pilot success metrics ("how many audits did the buyer actually run"), or
capacity planning depend on this, it isn't currently producing data.

### 9. A confirmed dead feature: policy trigger configuration

`policies`/`services/policy_service.py` has a full model/schema/service layer
but no HTTP endpoint anywhere exposes it (47 router files checked). Whatever
this was meant to let a tenant configure (per-policy latency budgets,
sampling rates, mirror-vs-block trigger modes — `models.py:1347-1383`), it
cannot be configured through the product today.

### 10. A few narrower, previously-noted gaps still open

Cross-checked against the prior 2026-06-15 gap analysis (`docs/GAP_ANALYSIS_2026-06-15.md`)
rather than assumed still valid — some of its items have since been fixed
(the S-1104 citation-leak bug is gone from `routers/scan.py`; `ai_incidents`
now has `fixed_by`/`fixed_at` columns), so only what's still verifiably true
is repeated here:
- No `/auth/refresh` endpoint — only per-tenant token expiry exists.
- Auth endpoints (`/auth/token`, magic-link) are exempted from the rate
  limiter — no brute-force/enumeration cap on login itself.
- `Reports.jsx` charts and PDF/CSV export are still UI placeholders
  ("Connect a charting library…") rather than wired to real data.
- The audit-chain rate limiter (`routers/audit_chain.py`) and the SAML
  replay-guard (`routers/sso.py`) are both in-memory and per-process —
  correctness would degrade if the app ever runs with multiple worker
  processes, which is a real risk for a product whose core value is
  tamper-evidence integrity.

---

## The honest summary

SARO solves a real, well-scoped problem — giving a compliance team
independent, evidence-based visibility into vendor AI output they're
otherwise accountable for on trust alone — and the core scan → score → TRACE
→ remediate loop for that problem is genuinely built and working. What's
missing clusters into three groups: **(a)** the external credibility layer
(SME validation) that would make the compliance evidence claim stand on its
own instead of being self-graded, **(b)** several concrete bugs in the exact
surfaces (Compliance Hub, board/vendor risk views, alerting) that the pilot's
named personas are supposed to rely on daily, and **(c)** capabilities implied
by the product's name and internal docs (statistical drift monitoring,
per-feature explainability, a unified AI-system inventory) that don't exist
yet and would need to be scoped as new work, not assumed to already be there.
