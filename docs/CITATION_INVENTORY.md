# SARO Framework Citation Inventory

> **Status:** v1.0 · Owner: Venky (Lead) · Reviewer: Jordan Lee · Last verified: 2026-06-12
> **Purpose (PT-003 / ISO 42001 Cl. 7.5):** single versioned source of truth for every framework
> citation SARO renders in product, reports, or exports. A one-time verification pass checked each
> citation against source text; the result (verified / corrected / removed) is recorded below.
> `scripts/check_citations.py` (run in CI and by `tests/test_pt003_citations.py`) fails the build if a
> rule-pack `rule_id` has no inventory entry, or if a forbidden misattribution reappears.

## Verification pass — summary (2026-06-12)

| Result | Count | Notes |
|---|---|---|
| verified | 17 | rule-pack `rule_id` citations confirmed against framework source text |
| corrected | 1 | 50-sample minimum was misattributed to EU AI Act Art. 10 / NIST MAP 2.3 → reattributed to internal methodology (SARO-METHOD-001) |
| removed | 0 | — |

Framework versions are pinned. Citations are labelled **"per"** only where the text is a literal
obligation of the cited section; **"informed by"** where SARO's mapping is interpretive.

## Internal methodology citations (NOT regulatory)

| Inventory ID | Claim | Correct source | Loci |
|---|---|---|---|
| SARO-METHOD-001 | 50-sample minimum for batch fairness/risk metrics | Internal SARO statistical methodology (CLT convergence; ~50/group for 80% power at α=0.05; TF-IDF stability). **NOT** EU AI Act Art. 10 and **NOT** NIST MAP 2.3. | `engine.py` `_gate1_data_quality`; `schemas.py` `BatchIn`/`SARoDataBatchIn`; `docs/COMPLIANCE_CLAIMS_MATRIX.md` §Sampling Methodology Basis |

## Regulatory / framework citations (rule packs)

Each row is a rule-pack `rule_id`. Framework version is pinned in the `version` field of the pack.

### NIST AI RMF 1.0 (`rule_packs/nist-ai-rmf/v1.0.0`)
| rule_id | Subcategory title | Usage | Status |
|---|---|---|---|
| MAP-2.3 | Scientific Findings on Fairness | per | verified |
| GOVERN-4.2 | Privacy Risk Management | per | verified |
| MEASURE-2.5 | Robustness and Reliability Testing | per | verified |
| GOVERN-1.6 | Third-Party Risk and Dual-Use | per | verified |
| MANAGE-4.1 | Post-Deployment Monitoring | per | verified |

### EU AI Act (`rule_packs/eu-ai-act/v1.0.0`)
| rule_id | Article | Usage | Status |
|---|---|---|---|
| ART_9 | Art. 9 — Risk management system | per | verified |
| ART_10 | Art. 10 — Data and data governance (training-data governance for high-risk systems) | per | verified |
| ART_10_3 | Art. 10(3) — Training-data quality criteria | per | verified |
| ART_50 | Art. 50 — Transparency obligations | per | verified |
| ART_5_1_B | Art. 5(1)(b) — Prohibited exploitation of vulnerabilities | per | verified |

> Note: ART_10 / ART_10_3 cite Art. 10's **training-data governance** obligations — they do **not**
> establish the 50-sample batch-audit threshold (that is SARO-METHOD-001).

### ISO/IEC 42001 (`rule_packs/iso-42001/v1.0.0`)
| rule_id | Annex A control | Usage | Status |
|---|---|---|---|
| ISO-A.6 | A.6 — AI system life cycle | informed by | verified |
| ISO-A.7 | A.7 — Data for AI systems | informed by | verified |
| ISO-A.9.3 | A.9.3 — Use / fairness controls | informed by | verified |
| ISO-A.10 | A.10 — Responsible use of AI | informed by | verified |

### AIGP (`rule_packs/aigp/v1.0.0`)
| rule_id | Principle | Usage | Status |
|---|---|---|---|
| AIGP-ETHICAL-1 | Ethical AI principle | informed by | verified |
| AIGP-PRIV-1 | Privacy principle | informed by | verified |
| AIGP-TRANS-1 | Transparency principle | informed by | verified |

## Adding a citation

Any new rule-pack `rule_id` (or new framework citation in product copy) **must** be added here in the
same change. CI (`scripts/check_citations.py`) fails otherwise. Pin the framework version and label
usage `per` (literal obligation) or `informed by` (interpretive mapping).
