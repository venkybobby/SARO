# SARO Compliance Claims Matrix v8.0.0

> **Purpose:** Defines the precise boundary between what SARO claims to do and what it explicitly does not claim. All compliance-related code, docs, and UI copy must conform to this matrix. Reference: [@.claude/skills/compliance-guard](.claude/skills/compliance-guard/SKILL.md)

---

## Decision Matrix

| Scenario | SARO Does | SARO Does NOT Do | Approved Language |
|---|---|---|---|
| Risk assessment | Computes 0–100 risk score from prompt + output | Determine if AI system is "safe" or "compliant" | "SARO scored this output at {score}/100" |
| NIST AI RMF | Maps findings to RMF function areas (Govern, Map, Measure, Manage) | Assert RMF conformance | "Evidence supporting NIST AI RMF Measure 2.5" |
| EU AI Act | Identifies characteristics associated with high-risk system categories | Classify a system as high-risk under EU law | "Indicators consistent with EU AI Act high-risk criteria" |
| ISO 42001 | Links scan records to document lifecycle stages | Issue ISO 42001 certificates | "Audit evidence for ISO 42001 document lifecycle review" |
| AIGP | Supports human reviewer workflows | Auto-certify under AIGP | "Evidence package for AIGP-certified human reviewer" |
| Audit trail | Generates immutable TRACE timelines | Guarantee audit admissibility | "TRACE record for human auditor review" |
| Hash chain integrity | Computes SHA-256 hash-chained audit traces; exposes chain verification endpoint (`GET /api/v1/audit/verify-chain`) | Guarantee tamper-proof storage or certify chain of custody | "TRACE chain integrity verifiable via SHA-256 hash chain — evidence for human auditor review" |
| Remediation | Provides guidance text | Guarantee remediation effectiveness | "Recommended remediation — human validation required" |
| Certification | Provides evidence packages | Issue, sign, or endorse certificates | "Supporting evidence — certification requires human authority" |

---

## Allowed vs. Forbidden Phrases

### In API Responses

| Allowed | Forbidden |
|---|---|
| `"framework_evidence": "NIST-AI-RMF-1.0"` | `"nist_compliant": true` |
| `"risk_score": 74` | `"compliance_score": 74` |
| `"remediation_guidance": "..."` | `"compliance_fix": "..."` |
| `"audit_evidence_generated": true` | `"audit_passed": true` |

### In UI Copy

| Allowed | Forbidden |
|---|---|
| "Risk score: 74/100 — human review recommended" | "Compliant: No" |
| "TRACE evidence generated for auditor review" | "Audit: Passed" |
| "Evaluated against NIST AI RMF criteria" | "NIST Certified" |

### In Documentation

| Allowed | Forbidden |
|---|---|
| "SARO provides audit evidence" | "SARO certifies compliance" |
| "Supports EU AI Act documentation workflows" | "Ensures EU AI Act compliance" |
| "Evidence-based risk scoring" | "Regulatory approval tool" |

---

## Framework Boundary Details

### NIST AI RMF 1.0
- SARO maps findings to: Govern 1.1, Map 1.1–1.6, Measure 2.1–2.13, Manage 1.3–4.2
- SARO does NOT: assess organisational governance maturity, validate policies, or issue RMF conformance statements

### EU AI Act
- SARO identifies: characteristics of prohibited practices, high-risk system indicators, transparency requirement gaps
- SARO does NOT: classify systems under Annexes I–III, make legal determinations, replace notified body assessment

### ISO 42001
- SARO provides: document lifecycle linkage, audit log records for Clause 9 (Performance Evaluation)
- SARO does NOT: certify management systems, conduct Stage 1/Stage 2 audits

### AIGP Principles
- SARO supports: human-in-the-loop workflows, evidence packaging for certified reviewers
- SARO does NOT: issue AIGP certifications, replace AIGP-certified human judgment

---

## EVF Validation Status (SARO-RISK-001)

> **Current status as of 2026-06-02:** No framework claim has completed External SME Validation (EVF). All four frameworks are in **Internal Review Only** state. No external compliance claim may be made until a Qualified Compliance Opinion (QCO) is issued per the EVF process (see `docs/SARO_GRC_SME_Validation_Requirements_v1.0.1.docx`).

| Framework | Locked Claim Scope | EVF Validation Status | QCO Reference | QCO Expiry |
|---|---|---|---|---|
| EU AI Act | Arts. 9, 13, 17 evidence support only | **Internal Review Only — Not for External Claim** | — | — |
| NIST AI RMF 1.0 | Govern, Map, Measure subcategory coverage | **Internal Review Only — Not for External Claim** | — | — |
| AIGP | Principles evaluation framework only | **Internal Review Only — Not for External Claim** | — | — |
| ISO 42001 | Document lifecycle linking and control objective support | **Internal Review Only — Not for External Claim** | — | — |

**Approved label tiers (FR-EVF-16):**
- **Tier 1** (QCO issued): `"Externally Reviewed — QCO [ref] | [SME Firm] | [Date]"`
- **Tier 2** (Under active SME review): `"SARO is undergoing independent review for [Framework] coverage. Claims will be published upon QCO completion."`
- **Tier 3** (Not assessed / current state): No compliance alignment reference permitted in external materials.

**Sales instruction (P-0 — effective immediately):** No new external compliance claims for any of the four frameworks until a QCO reference number is assigned. Demo scripts must use Tier 3 (omit framework alignment) or Tier 2 language only. See FR-EVF-11 and FR-EVF-16.

---

## Required Disclaimer (all reports)

> *"This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification, legal advice, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission."*

---

---

## Sampling Methodology Basis (SARO-002)

The 50-sample minimum enforced by SARO's Gate 1 is an **internal statistical heuristic**, not a regulatory requirement from EU AI Act Art. 10 or NIST MAP 2.3.

### Rationale

| Principle | Explanation |
|---|---|
| Central Limit Theorem convergence | With n < 50, sample means may not approximate the population mean reliably for fairness metric computation. |
| Statistical parity power | A two-group parity test needs approximately 50 samples per group for 80% power to detect a gap of 0.20 at α = 0.05 (Fisher's exact test). |
| TF-IDF similarity stability | TF-IDF vector representations become unstable with very small corpora; n ≥ 50 ensures meaningful incident matching query vectors. |

### Framework Boundary Clarification

| Claim | Correct |
|---|---|
| "EU AI Act Art. 10 requires 50 samples" | **False** — Art. 10 governs training data governance for high-risk systems; it sets no batch audit sample threshold. |
| "NIST MAP 2.3 requires 50 samples" | **False** — MAP 2.3 recommends scientific rigor in risk assessment; it sets no quantitative sample threshold. |
| "SARO requires 50 samples for statistical validity" | **Correct** — this is an internal methodology requirement, not a regulatory mandate. |

All Gate 1 error messages, schema docstrings, and remediation hints reference "internal SARO methodology" for the 50-sample requirement. EU AI Act Art. 10 and NIST MAP 2.3 citations are preserved only where the framework obligations are accurately described (Gate 2 fairness, Gate 4 compliance mapping).

---

*Last updated: 2026-06-02 | Owner: Venky (Lead) | Review: Jordan Lee (Backend) | EVF section added per SARO-RISK-001*
