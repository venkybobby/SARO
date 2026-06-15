# SARO External SME Validation Framework — Evidence Retention Addendum

> Implements **FR-EVF-20**. Defines retention periods and handling for all EVF artefacts:
> Evidence Packages, SME engagement records, QCOs, and publication audit trails. This addendum
> attaches to every Statement of Work (FR-EVF-04) and to the SARO Data Retention schedule.
> It does not constitute legal advice.

**Document control**

| Field | Value |
|---|---|
| Version | 1.0.0 (DRAFT — pending legal approval) |
| Owner | Venky (Product Owner) |
| Legal approval | [ ] Approved by: ____________________  Date: __________ |
| Supersedes | — |

---

## 1. Retention Schedule

| Artefact | Retention period | Rationale |
|---|---|---|
| Qualified Compliance Opinion (QCO) | **7 years** from issue date | Evidence trail for any claim made during validity. |
| QCO Registry records + publication events | **7 years** (append-only, immutable) | Tamper-evident provenance of every published claim. |
| Evidence Package shared with an SME | Duration of engagement **+ 14 days** | Minimise exposure of CONFIDENTIAL material (see SOW §7). |
| SME engagement + state-transition log | **7 years** | Auditability of who validated what, and when. |
| COI declarations | **7 years** | Independence evidence. |
| Challenge / claims-audit log entries | **7 years** | Demonstrates corrective action over time. |

## 2. Evidence Package Handling

- Evidence Packages are classified **CONFIDENTIAL** and shared under SOW confidentiality terms.
- The SME must return or securely destroy all Evidence Package materials within **14 days** of
  engagement completion; no retention beyond engagement close.
- SARO retains its own master copy of each Evidence Package under the 7-year schedule.

## 3. Immutability

QCO Registry rows and publication events are append-only and protected by a database trigger
blocking `UPDATE`/`DELETE` on published records. Corrections are made by issuing a superseding
record, never by mutating history.

## 4. Disposal

On expiry, artefacts are disposed of via the SARO Data Retention process (see
`docs/sample-evidence-retention.md`), with a dated disposal record retained for audit.

## 5. Cross-References

- Retention aligns with the SARO Data Retention schedule and DPA template (`docs/legal/`).
- The 7-year EVF retention is referenced by the DPA publication (S-1203) and the SOW template.

---

*Scope boundary: Retention of EVF evidence supports internal governance and auditability. It
does not extend or modify any compliance claim and confers no certification.*
