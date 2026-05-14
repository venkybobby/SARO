# SARO Data Processing Agreement Template

**IMPORTANT:** This template requires legal review before use with any customer. Contact legal counsel before signing.

**Version:** 1.0 | **Classification:** CONFIDENTIAL | **Last Updated:** May 2026

---

This Data Processing Agreement ("DPA") is entered into between:

**Data Controller:** [Customer Organization Name] ("Controller")  
**Data Processor:** SARO / [Legal Entity Name] ("Processor")

---

## Article 1: Subject Matter and Duration

The Processor shall process Personal Data on behalf of the Controller for the purpose of providing the SARO AI Risk Orchestration platform ("Service") for the duration of the service agreement.

---

## Article 2: Nature and Purpose of Processing

SARO processes the following categories of data:

### 2.1 Data Types Processed

| Category | Description | Legal Basis |
|----------|-------------|------------|
| Audit Input Data | AI model outputs submitted for risk assessment | Contractual necessity |
| Audit Metadata | Model name, version, submission timestamp | Contractual necessity |
| User Account Data | Email address, hashed password, role | Contractual necessity |
| Audit Results | Risk scores, findings, remediation steps | Contractual necessity |
| Session Data | JWT tokens, login timestamps | Legitimate interest (security) |

### 2.2 Categories of Data Subjects
- Employees of the Controller submitting AI outputs for audit
- End-users whose AI-generated outputs are submitted for review (indirect)

---

## Article 3: Obligations of the Processor (GDPR Article 28)

The Processor shall:

3.1 Process Personal Data only on documented instructions from the Controller.

3.2 Ensure that persons authorized to process Personal Data have committed to confidentiality.

3.3 Implement appropriate technical and organizational security measures per Article 32.

3.4 Not engage sub-processors without prior written consent of the Controller.

3.5 Assist the Controller in fulfilling data subject rights requests (access, rectification, erasure, portability).

3.6 Delete or return all Personal Data upon termination of services.

3.7 Make available all information necessary to demonstrate compliance with Article 28.

3.8 Allow for and contribute to audits conducted by the Controller or an appointed auditor.

---

## Article 4: Data Retention Periods

| Data Category | Retention Period | Basis |
|---------------|-----------------|-------|
| Audit records | 90 days (configurable per tenant) | Contractual |
| User accounts | Duration of contract + 30 days | Contractual |
| Deletion certificates | 7 years | Legal compliance |
| Security logs | 12 months | Legitimate interest |

Data may be purged earlier upon written GDPR erasure request.

---

## Article 5: Security Measures (Article 32)

The Processor implements:
- Encryption in transit (TLS 1.2+) and at rest (AES-256 via Supabase)
- Access control via JWT-based authentication with role-based permissions
- Row-Level Security (RLS) for tenant data isolation
- Regular automated security scanning (bandit, safety, TruffleHog)
- Tamper-evident hash-chained audit logs

---

## Article 6: Data Breach Notification

6.1 The Processor shall notify the Controller of a Personal Data Breach **without undue delay and within 72 hours** of becoming aware.

6.2 Notification shall include: nature of breach, categories of data affected, estimated number of data subjects, likely consequences, and remediation measures.

---

## Article 7: Sub-Processors

The Processor currently uses the following sub-processors (see docs/sub-processors.md for full inventory):

| Sub-Processor | Purpose | Location |
|--------------|---------|----------|
| Railway | Application hosting | US (with EU zone option) |
| Supabase | PostgreSQL database | US (with EU zone option) |
| Redis | Session management | Configured per deployment |

The Controller will be notified of sub-processor changes with 30 days notice.

---

## Article 8: International Transfers

Data transfers outside the EEA shall only occur under appropriate safeguards (SCCs, adequacy decisions).

---

## Article 9: Data Subject Rights

The Processor shall assist the Controller in responding to data subject requests within the statutory timeframes (30 days for GDPR).

---

## Article 10: Termination

Upon termination, the Processor shall delete all Controller Personal Data within 30 days and provide written confirmation of deletion.

---

*This template was prepared for legal review. Do not use without approval from qualified legal counsel.*
