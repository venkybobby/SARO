# SARO External SME Validation Framework — Claims Challenge Protocol

> Implements **FR-EVF-18**. Defines how any internal or external party may challenge a
> published SARO framework claim, and how SARO triages, adjudicates, and (if needed) retracts
> it. The objective is that no SARO compliance-alignment claim outlives the evidence and QCO
> that support it. This document does not constitute legal advice.

**Document control**

| Field | Value |
|---|---|
| Version | 1.0.0 (DRAFT — pending legal approval) |
| Owner | Venky (Product Owner) |
| Legal approval | [ ] Approved by: ____________________  Date: __________ |
| Supersedes | — |

---

## 1. Who May Challenge

Any customer, prospect, SME, employee, or regulator may raise a challenge against a published
claim (a label, badge, statement, or document asserting framework alignment or evidence
support).

## 2. How to Raise a Challenge

Submit to `governance@saro` (or the in-product feedback channel) with: the exact claim text,
where it appears (artefact + version), and the basis for the challenge.

## 3. Triage and Severity

| Severity | Definition | Initial response |
|---|---|---|
| Critical | Claim overstates assurance (e.g. implies certification/conformity) or cites a wrong regulation. | Within 2 business days; claim suspended pending review. |
| High | Claim's supporting QCO is expired, withdrawn, or out of scope. | Within 5 business days. |
| Medium | Ambiguous or potentially misleading wording. | Within 10 business days. |

## 4. Adjudication

1. The Product Owner verifies the claim against the QCO Registry and the Compliance Claims
   Matrix (`docs/COMPLIANCE_CLAIMS_MATRIX.md`).
2. If the claim lacks a current QCO or exceeds the locked scope, it is **downgraded** to the
   appropriate approved tier (FR-EVF-16) or **removed entirely** (Tier 3).
3. For factual disputes about framework coverage, the relevant SME is consulted.

## 5. Resolution and Record

- Every challenge and its disposition is logged in `docs/CLAIMS_AUDIT_LOG.md` with date,
  challenger (anonymised if requested), claim, decision, and remediation reference.
- A corrected artefact is re-published with a new version; history is superseded, never
  silently edited.
- The challenger receives a written outcome.

## 6. Escalation

Unresolved challenges escalate to SARO Legal Counsel. A challenge alleging a regulatory
misrepresentation is treated as Critical regardless of initial classification.

---

*Scope boundary: This protocol governs the accuracy of SARO's own claims. It does not
adjudicate a customer's regulatory status and is not a substitute for the customer's own
compliance review.*
