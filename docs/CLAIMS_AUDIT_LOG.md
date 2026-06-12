# Retrospective Claims Audit Log (FR-EVF-17)

> **Status:** v1.0 · CANONICAL · Owner: Venky (Lead) · 2026-06-12 · PT-005 AC-3
> Maps every external-facing compliance claim (sales deck, demo script, website, docs) to a
> disposition: **VERIFIED** / **CORRECTED** / **WITHDRAWN**. Derived from
> `docs/evf/evf_retrospective_audit_2026-06-02.json` and the Compliance Claims Matrix.

## Disposition summary

| Disposition | Count | Meaning |
|---|---|---|
| VERIFIED | — | Claim is accurate as stated and within the approved language tiers. |
| CORRECTED | — | Claim was reworded to evidence-support language (no certification implied). |
| WITHDRAWN | — | Claim removed entirely (overclaim with no supportable basis). |

## Claims ledger

| # | Claim (as found) | Source | Disposition | Resolution | Owner | Date |
|---|---|---|---|---|---|---|
| 1 | "ISO 42001 certification support" | ADR-004 / matrix row | CORRECTED | SARO never certifies; reworded to "document-lifecycle linkage / audit evidence" (matrix-aligned) | Venky | 2026-06 |
| 2 | "50-sample minimum per EU AI Act Art. 10 / NIST MAP 2.3" | engine / schema copy | CORRECTED | Reattributed to internal SARO methodology (SARO-METHOD-001, CITATION_INVENTORY) | Alex Rivera | 2026-06 |
| 3 | "NIST AI RMF aligned" (unqualified) | reports / decks | CORRECTED | Replaced with mechanically-derived "N of 68 subcategories, map v1.0" (PT-007) | Alex Rivera | 2026-06 |
| 4 | Any framework "Externally Reviewed / QCO" claim | sales materials | WITHDRAWN until QCO issued | All four frameworks remain **Internal Review Only** until a QCO reference is assigned (matrix §EVF; Tier-3/Tier-2 language only) | Venky | 2026-06 |
| 5 | Infrastructure claims (Railway / Neon "in production") | decks / context docs | CORRECTED | Canonical stack is Fly.io + Supabase (ARCHITECTURE.md); legacy refs marked SUPERSEDED | Jordan Lee | 2026-06 |

## Process

- The forbidden-phrase scanner (`scripts/evf_retrospective_audit.py`) runs over the repo; new
  violations are logged here before release.
- External materials must use only the approved language tiers in `COMPLIANCE_CLAIMS_MATRIX.md`
  (Tier 3 / Tier 2 only until a QCO is issued).
- Externally-shared documents are corrected via **errata**, never silent revision.
