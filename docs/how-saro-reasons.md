# How SARO Reasons

**Version:** 1.0 | **Last Updated:** May 2026

This document explains exactly how SARO produces risk scores and findings for every AI output it analyses.

---

## Overview

SARO uses a four-gate sequential analysis pipeline. Each AI output submitted for audit passes through all four gates before receiving a final risk score and findings summary.

---

## Analysis Methodology

### Gate 1: Data Quality (Ingest)

SARO first validates the structure and completeness of the submitted AI output:
- **Field completeness:** Required fields (model_id, output_text, context) are present
- **Length bounds:** Output length is within expected ranges for the declared model type
- **Encoding:** Text is valid UTF-8 with no control characters
- **Metadata:** Submission timestamp, tenant ID, and model version are recorded

If data quality fails, the audit is flagged and subsequent gates are skipped.

### Gate 2: Fairness & EU AI Act Classification (Classify)

SARO evaluates the AI output against fairness principles and EU AI Act risk categories:
- **Protected attributes:** Detects references to protected characteristics (age, gender, ethnicity, religion, disability) using keyword and pattern matching
- **EU AI Act Annex III:** Classifies output against 8 high-risk AI categories (biometric ID, critical infrastructure, education, employment, essential services, law enforcement, migration, justice)
- **Differential impact:** Compares treatment of named groups using co-occurrence analysis
- **Confidence:** Calculated as the proportion of rules evaluated without ambiguity

### Gate 3: MIT Risk Matching (Match)

SARO matches the output against the MIT AI Risk taxonomy using TF-IDF similarity search:
- **Incident database:** SARO maintains a database of known AI incidents categorised by risk domain
- **TF-IDF scoring:** Cosine similarity between the submitted output and incident descriptions
- **Threshold:** A similarity score above 0.35 triggers a risk flag for that domain
- **Domains:** Safety, Fairness, Privacy, Transparency, Accountability, Security

### Gate 4: Compliance Rule Matching (Score)

SARO evaluates the output against the active rule packs (NIST RMF, EU AI Act, AIGP, ISO 42001):
- **Rule matching:** Each rule is evaluated as a boolean (fired / not fired) against the output
- **Weighted scoring:** Each rule has a weight (1–5) based on regulatory severity
- **Bayesian risk score:** SARO uses a Beta posterior model. Prior: Beta(2, 5). Each fired rule updates the posterior. Final score = posterior mean × 100
- **Credible interval:** 90% HDI (highest density interval) is computed and reported as confidence bounds

---

## How Risk Scores Are Calculated

1. Start with a Beta(2, 5) prior — representing a "mostly safe" prior belief
2. For each rule that fires, add to the "failure" count (alpha parameter)
3. For each rule that does not fire, add to the "success" count (beta parameter)
4. Final risk score = (posterior alpha / (alpha + beta)) × 100
5. Confidence = width of the 90% HDI (narrower = higher confidence)

**Interpretation:**
- 0–29: LOW risk (GREEN)
- 30–69: MEDIUM risk (AMBER)
- 70–100: HIGH risk (RED)

---

## What "Confidence" Means

Confidence in SARO refers to the width of the Bayesian credible interval:
- **High confidence (>0.85):** The risk score is well-supported by the evidence. Multiple rules evaluated cleanly.
- **Medium confidence (0.65–0.85):** Some rules produced ambiguous signals. Human review recommended.
- **Low confidence (<0.65):** Insufficient data or high ambiguity. The score should be treated as indicative only.

---

## What SARO Does NOT Do

- **SARO does not read or store your raw AI training data.** Only the submitted outputs are analysed.
- **SARO does not make legal determinations.** Risk scores are analytical aids, not legal opinions.
- **SARO does not certify compliance.** A SARO "pass" does not mean regulatory approval.
- **SARO does not perform conformity assessments** under the EU AI Act (Article 43).
- **SARO does not replace human oversight.** All high-risk findings should be reviewed by a qualified professional.
- **SARO does not retain outputs** beyond the configured retention period.
- **SARO does not share your data** with other tenants (enforced by Row-Level Security).

---

## Reproducibility

Every audit produces a TRACE record that captures:
- Which version of each rule pack was active
- Which rules fired and which did not
- The exact risk score calculation inputs
- The Bayesian posterior parameters

This record is tamper-evident (SHA-256 hash chain) and can be exported as a signed evidence pack (HMAC-SHA256 + RFC 3161 timestamp).

---

*This document is version-controlled in docs/how-saro-reasons.md. Questions: contact the SARO product team.*
