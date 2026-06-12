> **[SUPERSEDED]** by `docs/legal/saro-dpa-template-v1.0.md` (canonical DPA). Retained for history. Infrastructure references (Neon) are superseded by `docs/ARCHITECTURE.md`. See `docs/DOCUMENT_REGISTER.md`.

# SARO Interim Data Processing Agreement — v0

**Classification:** CONFIDENTIAL  
**Version:** 0.1-interim | **Date:** 2026-05-28  
**Status:** Signable interim document — replace with full DPA (docs/dpa-template.md) once legal review is complete.

---

This Interim Data Processing Agreement ("Agreement") is entered into between:

**Data Controller:** _________________________________ ("Controller")  
**Data Processor:** SARO / [Legal Entity Name] ("Processor")

Effective date: _________________________________

---

## 1. Subject Matter

The Processor provides the SARO AI Risk Orchestration platform ("Service"), which processes Personal Data solely to deliver risk assessment, audit trail, and evidence-package services on behalf of the Controller.

---

## 2. GDPR Article 28 Obligations

The Processor shall:

**2.1** Process Personal Data only on documented instructions from the Controller, and for no other purpose.

**2.2** Ensure that all personnel authorised to process Personal Data are bound by confidentiality obligations.

**2.3** Implement appropriate technical and organisational security measures (see §4).

**2.4** Not engage sub-processors without prior written authorisation of the Controller (see §5 for current approved list).

**2.5** Assist the Controller — by appropriate technical and organisational measures, insofar as possible — in fulfilling its obligations to respond to data subject rights requests (access, rectification, erasure, restriction, portability, objection).

**2.6** Delete or return all Personal Data to the Controller upon termination of the Agreement, and delete existing copies unless EU or Member State law requires retention.

**2.7** Make available all information reasonably necessary to demonstrate compliance with Article 28, and allow for and contribute to audits or inspections conducted by the Controller or a mandated auditor, on reasonable notice.

---

## 3. Categories of Data Processed

| Category | Description |
|---|---|
| Audit input data | AI model outputs submitted for risk assessment |
| Audit metadata | Model name, version, submission timestamp, batch identifier |
| User account data | Email address (hashed password, role) |
| Audit results | Risk scores, findings, remediation guidance |

Personal data of end-users whose AI-generated outputs are submitted for review is processed only in aggregate and is not linked to identifiable individuals by SARO.

---

## 4. Security Measures (Article 32)

- TLS 1.2+ encryption in transit; AES-256 at rest via Supabase
- JWT-based authentication with role-based access control (RBAC)
- Row-Level Security (RLS) enforcing tenant data isolation
- Cryptographically signed audit logs (HMAC-SHA256)
- Automated vulnerability scanning (bandit, pip-audit, TruffleHog) on every deployment
- Access limited to personnel on a need-to-know basis

---

## 5. Approved Sub-Processors

| Sub-Processor | Purpose | Data Location |
|---|---|---|
| **Railway** | Application hosting and compute | US (EU-region deployment available on request) |
| **Supabase** | PostgreSQL database (primary) | US (EU-region deployment available on request) |
| **Neon** | PostgreSQL database (serverless / read replicas) | US (EU-region deployment available on request) |
| **Redis (Railway-managed)** | Session management and rate limiting | Same region as application |

The Processor will provide **30 days written notice** before adding or replacing a sub-processor. The Controller may object in writing within 14 days; unresolved objections entitle the Controller to terminate without penalty.

---

## 6. Data Breach Notification (Article 33)

The Processor shall notify the Controller of any Personal Data Breach **without undue delay and in any event within 72 hours** of becoming aware. Notification shall include, to the extent then known:

- The nature of the breach and the categories and approximate number of data subjects and records affected
- The name and contact details of the data protection point of contact
- The likely consequences of the breach
- Measures taken or proposed to address the breach and mitigate its effects

---

## 7. Data Retention

Audit records are retained for **90 days** by default (configurable per tenant on written request). All Personal Data is deleted or returned within **30 days** of contract termination unless longer retention is required by applicable law.

---

## 8. Governing Law

This Agreement is governed by the law of [Processor's jurisdiction — to be completed]. Disputes shall be subject to the exclusive jurisdiction of [courts — to be completed].

---

## 9. Signatures

| Party | Name | Title | Signature | Date |
|---|---|---|---|---|
| Controller | | | | |
| Processor | | | | |

---

*This interim DPA covers GDPR Article 28 essentials and is designed for immediate use while the full DPA (docs/dpa-template.md) undergoes legal review. It does not cover all scenarios; customers with specific requirements (SCCs, BCRs, sector-specific obligations) should request the full DPA.*
