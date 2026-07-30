# SARO Knowledge Base

Generated 2026-07-29 by a zero-hallucination code audit — every claim in these
documents is grounded in a specific file:line citation from the actual
repository or a live query against the production Supabase project
(`fktfhtygvwqlmoazmhdf`). Nothing here is inferred from CLAUDE.md, skill
files, or prior chat history without independent verification against code —
in several places those documents turned out to describe things that don't
exist (see [DOCS_VS_CODE_GAPS.md](DOCS_VS_CODE_GAPS.md)).

**Purpose:** SARO's owner lost track of what the product actually does after
four months of development. This knowledge base is the recovery artifact —
read it instead of relying on memory, chat history, or the aspirational
sections of CLAUDE.md.

## Documents

| File | Covers |
|---|---|
| [PURPOSE_AND_GAPS.md](PURPOSE_AND_GAPS.md) | **Start here for "what is SARO for."** The core problem it solves (per the team's own pilot positioning), how it solves it, and a grounded list of what it's not solving yet |
| [FEATURE_CATALOG.md](FEATURE_CATALOG.md) | Every feature area, grouped by function — what it does, which endpoints/tables/frontend pages implement it, and known bugs/gaps in each |
| [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) | The real role/persona system, what each role can actually do, and where "Implementation Lead" / "Risk Auditor ISO 42001" stand (spoiler: nowhere in code) |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | All 61 live Supabase tables, what each is for, row counts, and — for the ~28 empty ones — why they're empty |
| [DOCS_VS_CODE_GAPS.md](DOCS_VS_CODE_GAPS.md) | Places where CLAUDE.md / `.claude/skills/*` describe a feature (DIR formula, SHAP, KS-test drift) that does not exist in `engine.py` |
| [RULE_SETS_IMPLEMENTATION_STATUS.md](RULE_SETS_IMPLEMENTATION_STATUS.md) | How `eu_ai_act_rules` / `nist_ai_rmf_controls` / `aigp_principles` / `governance_rules` are actually built and used — and why none of them currently drive live scoring |

## How this was built

Five parallel code-exploration passes (routers/, models.py + schemas.py +
migrations, auth.py + role enforcement, engine.py + rule_packs/, frontend/)
plus direct SQL against the live Supabase project. Every finding was required
to cite a file:line or a query result; anything that couldn't be verified is
marked as such rather than guessed at.

## Top-line findings worth knowing before you read anything else

1. **Three role names, three different fates.** Of "Implementation Lead",
   "AI Auditor", and "Risk Auditor ISO 42001" — only `ai_auditor` exists as a
   real, enforced persona. "Implementation Lead" has zero code footprint.
   "Risk Auditor ISO 42001" has zero code footprint (the closest real thing
   is the `risk_officer` persona; "ISO 42001" itself is a compliance
   framework name, not a role). See [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md).
2. **The frontend has two competing role vocabularies.** The real app uses
   `compliance_lead / risk_officer / ai_auditor / admin / super_admin /
   operator` throughout. But `frontend/src/pages/Settings.jsx` independently
   hardcodes a *different* set — "Admin / Risk Manager / Viewer / Auditor" —
   with zero backend wiring. This is almost certainly the source of the "roles
   not defined properly in UI" confusion.
3. **A real access-control bug**: the Compliance Hub endpoint
   (`GET /api/v1/compliance/hub`) currently denies every persona, including
   the ones it's supposed to allow, because of an argument-unpacking bug in
   `auth.py`'s `persona_required()`.
4. **CLAUDE.md overclaims the scoring engine.** The documented "DIR formula",
   SHAP explainability, and KS-test/2σ drift detection do not exist anywhere
   in `engine.py`. What's actually implemented is a 4-gate pipeline producing
   a Bayesian Beta-Binomial posterior score — a real, different, working
   mechanism.
5. **~28 of 61 Supabase tables are empty**, but almost all of that is
   explainable: features that are fully wired end-to-end but simply haven't
   been used yet (nobody has configured GitHub integration, registered an AI
   system, engaged an SME firm, etc.). A small number are genuine gaps —
   notably the `policies` table, which has a full model/schema/service layer
   but **no HTTP endpoint anywhere exposes it**, so it can never receive data
   through the API. Full breakdown in [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).
