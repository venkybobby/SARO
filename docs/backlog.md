# SARO Product Backlog

*Owner: Venky (Lead) | Updated: 2026-05-28 | Format: Epic → Stories*

---

## Epic 10 — Adversarial AI Output Detection

**Status:** Backlog — not yet scheduled  
**Priority:** High (reputational / procurement risk)  
**Raised by:** Pre-sales risk review, 2026-05-28

### Problem Statement

SARO analyses AI model outputs for risk — but it currently has no ability to detect when those outputs are themselves adversarially crafted to *evade* SARO's detection. This creates a quiet blind spot:

- A bad actor could craft model outputs that score low in SARO's 4-gate pipeline while still containing harmful content (e.g. jailbreak payloads, encoded instructions, steganographic text, prompt injection fragments).
- SARO can be positioned by a sophisticated user as a "cleared by SARO" cover for outputs it was never designed to evaluate at the adversarial layer.
- This does not require SARO to be hacked — it requires SARO to be *used as intended* by someone who has reverse-engineered its scoring logic.

A well-prepared procurement team at a regulated customer (financial services, healthcare, defence) will ask about this directly. Without an answer, the question becomes a blocker.

### Scope

This epic does **not** change SARO's core posture (read-only, no external model calls, human-in-the-loop). It adds a detection layer within the existing 4-gate pipeline.

### Proposed Stories

| ID | Story | Acceptance Criteria |
|---|---|---|
| E10-S1 | **Adversarial pattern signal library** — build a rule pack of known adversarial output patterns (Base64-encoded instructions, homoglyph substitution, invisible Unicode, jailbreak phrasing, prompt injection templates) | Rule pack passes schema validation; fires on ≥ 3 known adversarial examples from public benchmarks |
| E10-S2 | **Gate 3 adversarial sub-check** — add an `adversarial_evasion` check type to the MIT risk gate that runs the signal library against each sample | Check appears in TRACE timeline; `check_type = "adversarial_evasion"` |
| E10-S3 | **Evasion confidence score** — derive a per-sample evasion likelihood score (0.0–1.0) that feeds into the Bayesian posterior as a weighted signal | Score visible in `detail_json`; weight configurable in rule pack |
| E10-S4 | **Adversarial findings in AuditReportOut** — surface evasion findings in the report response and TRACE export | `adversarial_findings: list[SampleFinding]` added to `AuditReportOut`; no breaking schema change |
| E10-S5 | **Remediation guidance for evasion indicators** — provide human-reviewer remediation hints when evasion signals fire | Guidance text references "human review required — automated scoring may underestimate risk" |
| E10-S6 | **Disclosure language** — update COMPLIANCE_CLAIMS_MATRIX.md and compliance-claims.md to accurately describe what SARO does and does not detect at the adversarial layer | No overclaiming; approved language: "SARO flags indicators consistent with adversarial output patterns — human review is required to confirm evasion intent" |
| E10-S7 | **Benchmark evaluation** — evaluate rule pack against HarmBench, AdvBench, and SARO's existing HF sample queue | Precision ≥ 0.70, recall ≥ 0.60 on labelled adversarial set; results in `saro-data-framework/evals/` |

### What SARO Will NOT Claim

- SARO does not guarantee detection of novel adversarial techniques
- SARO does not replace red-teaming or dedicated adversarial ML evaluation
- Scores remain advisory; human sign-off is always required

### Dependencies

- E10-S1 requires rule pack schema v2 (versioned weight field) — coordinate with `rule-pack-edit` skill
- E10-S3 requires Bayesian engine changes — coordinate with Alex Rivera (ML)
- E10-S7 requires access to HarmBench labels — confirm licensing before ingesting

### Out of Scope

- Real-time adversarial detection during model inference (SARO is post-hoc only)
- Generating adversarial examples (offensive capability — not in SARO's posture)
- Detecting adversarial *training data* (separate from output detection)

---

*Add new epics below this line, numbered sequentially.*
