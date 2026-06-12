# NIST AI RMF 1.0 — Coverage Status Rubric

> **Status:** v1.0 · Owner: Alex Rivera (ML) · Reviewer: Venky (Lead) · 2026-06-12
> Companion to `GET /api/v1/reports/nist-coverage` (PT-007 / STORY-011).
> Coverage is **honest by construction**: the `mapped` set is derived mechanically from the
> engine's `_COMPLIANCE_TRIGGERS`, not asserted. This document defines the four status tiers so
> "partial" can never be used without a written basis.

## Why this exists

SARO covers a small, verifiable slice of NIST AI RMF (currently 12 of 68 subcategories are
`mapped`). Publishing the honest map converts an over-claim risk into a trust asset: a buyer can
mechanically check the claim against the code.

## Status tiers

| Status | Definition | How it is decided |
|---|---|---|
| `mapped` | SARO generates automated evidence for this subcategory from prompt+output text analysis. | **Derived from code.** A subcategory is `mapped` iff at least one active `_COMPLIANCE_TRIGGERS` entry carries its `nist_subcategory_id`. Counted once per subcategory regardless of how many triggers map to it. Pinned by `tests/test_pt007_nist_coverage.py`. |
| `partial` | SARO produces a *related* automated signal that informs, but does not by itself evidence, the subcategory; human review required to close the gap. | **Curated, rubric-gated.** Requires a documented basis in this file (see "Partial entries" below). Never the default. |
| `requires_human_assessment` | No automated signal is possible from text analysis (governance/process/organizational subcategories). | Curated default for governance/process outcomes. |
| `not_covered` | Reserved — a subcategory present in the canonical set but absent from the curated map. | Should not occur while the map is complete (68/68). |

## Partial entries (the only subcategories permitted to use `partial`)

Each `partial` must have a one-line basis here. Adding a `partial` without a basis row should fail review.

| Subcategory | Basis for `partial` |
|---|---|
| GOVERN 1.1 | Risk-tolerance signals surface indirectly via overall risk score; policy linkage is manual. |
| GOVERN 6.2 | Third-party/dual-use signals (Malicious Use domain) partially inform supply-chain review. |
| MAP 5.1 | Impact-characterization is partially informed by domain risk weighting; context is manual. |
| MEASURE 2.11 | Fairness/bias detection contributes evidence; full fairness assessment is manual. |

> Any change to the `mapped` set (e.g., adding/removing a rule-pack trigger) automatically changes the
> derived coverage and is caught by CI via the pinning test — the published count moves with reality.

## Boundary (per COMPLIANCE_CLAIMS_MATRIX)

This map is **evidence support**, not a conformance statement. No report may emit an unqualified
"NIST AI RMF aligned" string; the coverage count and map version travel with every claim.
