# SARO Data Processing Agreement — Template v1.0

**Document version:** 1.0  
**Status:** TEMPLATE — requires legal review and completion before use with any customer  
**Legal review required:** Yes — fill in `[LEGAL REVIEW DATE]` and `[REVIEWER NAME]` once reviewed  
**Last updated:** 2026-05-22  
**Owner:** Venky (Lead Engineer)  

> ⚠️ **THIS IS A TEMPLATE.** All placeholders in `[BRACKETS]` must be completed before use.  
> Legal sign-off is mandatory — see `docs/legal/reviews/` for the sign-off record.

---

## DATA PROCESSING AGREEMENT

This Data Processing Agreement ("DPA") is entered into between:

**Controller:** `[CUSTOMER LEGAL ENTITY NAME]`, a company incorporated under the laws of `[JURISDICTION]`, with registered address at `[ADDRESS]` ("Controller"); and

**Processor:** `[SARO LEGAL ENTITY NAME]`, incorporated under the laws of `[JURISDICTION]`, with registered address at `[ADDRESS]` ("Processor").

This DPA forms part of and is subject to the Master Services Agreement ("MSA") or other binding agreement between the parties dated `[CONTRACT DATE]`.

---

## ARTICLE 1 — DEFINITIONS

1.1 "**Personal Data**" means any information relating to an identified or identifiable natural person within the meaning of GDPR Article 4(1).

1.2 "**Processing**" has the meaning given in GDPR Article 4(2).

1.3 "**GDPR**" means the General Data Protection Regulation (EU) 2016/679 and, where applicable, its UK equivalent (UK GDPR).

1.4 "**Sub-processor**" means any processor engaged by the Processor to process Personal Data on behalf of the Controller.

1.5 "**SARO Platform**" means the AI risk auditing software-as-a-service operated by the Processor, which ingests `prompt` and `raw_output` text submitted by the Controller, produces risk scores and audit evidence, and stores audit metadata.

---

## ARTICLE 2 — SCOPE AND PURPOSE (GDPR Article 28(3))

2.1 The Processor shall process Personal Data solely on documented instructions from the Controller, including with regard to transfers of Personal Data to a third country, unless required to do so by Union or Member State law.

2.2 The subject-matter of processing is the provision of AI risk auditing services via the SARO Platform.

2.3 The duration of processing is for the term of the MSA plus any applicable retention period set out in Schedule 1.

2.4 The nature and purpose of processing: analysis of AI model outputs and prompts submitted by the Controller to generate risk scores, TRACE audit timelines, and compliance evidence packages. SARO does not train AI models on Controller data.

2.5 The type of Personal Data and categories of data subjects are set out in **Schedule 1**.

---

## ARTICLE 3 — CONTROLLER INSTRUCTIONS

3.1 The Processor shall process Personal Data only on documented instructions from the Controller.

3.2 The Processor shall inform the Controller immediately if, in its opinion, an instruction infringes the GDPR or other applicable data protection law.

---

## ARTICLE 4 — CONFIDENTIALITY

4.1 The Processor shall ensure that persons authorised to process Personal Data have committed themselves to confidentiality or are under an appropriate statutory obligation of confidentiality.

---

## ARTICLE 5 — SECURITY MEASURES (GDPR Article 28(3)(c))

See **Schedule 2** for technical and organisational security measures.

5.1 The Processor shall implement and maintain the technical and organisational measures described in Schedule 2 to protect Personal Data against accidental or unlawful destruction, loss, alteration, unauthorised disclosure, or access.

5.2 The Processor shall notify the Controller without undue delay (and within 72 hours) after becoming aware of a personal data breach affecting data processed under this DPA.

---

## ARTICLE 6 — SUB-PROCESSORS (GDPR Article 28(2))

6.1 The Controller grants the Processor general authorisation to engage the Sub-processors listed in **Schedule 3**.

6.2 The Processor shall inform the Controller of any intended changes concerning the addition or replacement of Sub-processors, giving the Controller the opportunity to object.

6.3 The Processor shall impose data protection obligations on each Sub-processor by way of a contract that provides the same level of protection as this DPA.

---

## ARTICLE 7 — DATA SUBJECT RIGHTS

7.1 The Processor shall assist the Controller, by appropriate technical and organisational measures, with fulfilling the Controller's obligation to respond to requests from data subjects exercising their rights under Chapter III of the GDPR.

7.2 The Processor provides a GDPR Article 17 erasure API endpoint (`POST /api/v1/governance/erasure-request`) for deletion requests with a 72-hour SLA.

---

## ARTICLE 8 — DATA PROTECTION IMPACT ASSESSMENT

8.1 The Processor shall assist the Controller in carrying out data protection impact assessments (DPIA) under GDPR Article 35 where required.

---

## ARTICLE 9 — DELETION AND RETURN OF DATA

9.1 At the choice of the Controller, the Processor shall delete or return all Personal Data upon termination of the MSA, and delete existing copies unless Union or Member State law requires storage.

9.2 Default retention periods are set out in Schedule 1.

---

## ARTICLE 10 — AUDIT AND INSPECTION

10.1 The Processor shall make available to the Controller all information necessary to demonstrate compliance with GDPR Article 28, and shall allow for and contribute to audits conducted by the Controller or a mandated auditor, subject to reasonable notice (minimum 30 days) and confidentiality obligations.

10.2 The Processor may satisfy audit obligations by providing its SOC 2 Type II report (when available) or equivalent third-party audit report.

---

## ARTICLE 11 — DATA TRANSFERS

11.1 Current hosting region: Railway US-West (United States). EU hosting is available on request — contact `[SARO SUPPORT EMAIL]`.

11.2 Transfers of Personal Data to countries outside the EEA are governed by appropriate safeguards, including Standard Contractual Clauses (SCCs) as adopted by the European Commission.

---

## SCHEDULE 1 — DATA PROCESSING ACTIVITIES

| Field | Detail |
|---|---|
| **Data controller** | `[CUSTOMER NAME]` |
| **Data processor** | `[SARO LEGAL ENTITY]` |
| **Subject-matter** | AI risk auditing of AI model outputs |
| **Duration** | Term of MSA + `[3]` years retention for audit records (see below) |
| **Nature of processing** | Storage, analysis, risk scoring, audit evidence generation |
| **Purpose** | AI governance, risk management, regulatory compliance evidence |

### Categories of Personal Data Processed

| Category | Examples | Present in SARO? |
|---|---|---|
| AI model prompts and outputs | Text submitted by Controller for auditing | Yes — stored as audit record |
| User account data | Email address, role, login timestamps | Yes — SARO user accounts |
| Audit metadata | Dataset name, risk scores, timestamps | Yes — core product data |
| IP addresses | API request logs | Yes — system logs (transient) |

> **Important:** SARO does not require Controllers to submit personal data. Controllers should apply appropriate data minimisation before submitting samples to SARO. If samples contain personal data (e.g. AI outputs that include PII), SARO applies automatic PII redaction in TRACE records.

### Categories of Data Subjects

- Employees and authorised users of the Controller using the SARO Platform
- Individuals whose personal data appears incidentally in AI model outputs submitted for auditing (Controller responsibility to minimise)

### Retention Periods

| Data Type | Retention Period | Configurable? |
|---|---|---|
| Audit records (risk scores, TRACE timelines) | `[3]` years | Yes — via `POST /api/v1/governance/retention-policy` |
| Raw sample text (if stored) | Audit run duration only by default | Yes — opt-in persistent storage |
| User account data | Duration of account + 90 days | No |
| System logs | 30 days | No |

> **Note:** The `[3]` year default aligns with the shortest audit record retention requirement across Finance, Healthcare, and Government verticals. Controllers in longer-retention sectors (e.g. financial services — 5–7 years) must configure the retention policy accordingly.

---

## SCHEDULE 2 — TECHNICAL AND ORGANISATIONAL SECURITY MEASURES

### Access Controls
- Authentication: Argon2id password hashing (new accounts); bcrypt legacy fallback
- Session management: JSON Web Tokens (JWT) with configurable expiry
- Role-based access control (RBAC): super_admin, operator, persona-based permissions
- SSO/SAML 2.0 available for enterprise tenants (SAML signature validation enforced)
- MFA: configurable per tenant via `ClientConfig.mfa_required`

### Data in Transit
- All API communication over TLS 1.2+ (enforced by Railway infrastructure)
- HSTS enforced on all endpoints

### Data at Rest
- Hosted on Railway (US-West by default; EU region available on request)
- PostgreSQL database via Neon/Supabase with encryption at rest
- Jira integration tokens encrypted using Fernet (AES-128-CBC) with key derived from deployment secret

### Monitoring and Incident Response
- Audit event logging: all authentication events, SSO events, data exports, and configuration changes are written to the immutable `audit_events` table
- Incident response plan: `docs/incident-response-plan.md`
- Sentry error monitoring (configurable via `SENTRY_DSN`)

### Development Practices
- Pre-commit hooks enforce security linting (ruff, pip-audit)
- No secrets committed to git (enforced via pre-commit checks)
- Dependency vulnerability scanning via `pip-audit` (scheduled weekly in CI)

---

## SCHEDULE 3 — SUB-PROCESSOR LIST

| Sub-processor | Purpose | Location | DPA/Terms |
|---|---|---|---|
| **Railway** | API hosting and compute | United States | Railway DPA (see railway.app/legal/dpa) |
| **Neon / Supabase** | PostgreSQL database hosting | United States (EU region available) | Supabase DPA (see supabase.com/legal/dpa) |
| **SendGrid (Twilio)** | Transactional email notifications | United States | Twilio DPA (see twilio.com/legal/data-protection-addendum) |
| **Anthropic** | LLM-as-judge risk classification (optional — only if enabled for tenant) | United States | Anthropic usage policies — **scope limited to text classification during audit runs; Anthropic does not train on customer data** |

> **Anthropic note:** The Anthropic API is used only when the LLM-as-judge hybrid classifier is enabled for a tenant (`ANTHROPIC_API_KEY` configured). Text submitted to the Anthropic API is limited to AI model output samples (truncated to 500 characters) for the purpose of risk domain classification. Anthropic's zero data retention policy applies.

---

## SCHEDULE 4 — DATA RESIDENCY OPTIONS

| Option | Region | Notes |
|---|---|---|
| Default | US-West (Railway) | Standard tier |
| EU hosting | EU-West (Railway Frankfurt) | Available on request — requires re-provisioning |

Controllers with EU data residency requirements must request EU hosting before initial deployment.

---

## SIGNATURES

**On behalf of the Controller:**

Signed: ___________________________  
Name: `[NAME]`  
Title: `[TITLE]`  
Date: `[DATE]`  

**On behalf of the Processor (SARO):**

Signed: ___________________________  
Name: `[NAME]`  
Title: `[TITLE]`  
Date: `[DATE]`  

---

## LEGAL REVIEW RECORD

| Field | Value |
|---|---|
| Reviewer name | `[LEGAL REVIEW DATE — REQUIRED BEFORE USE]` |
| Review date | `[DATE]` |
| Review scope | GDPR Article 28(3) compliance, sub-processor accuracy, retention periods |
| Sign-off document | `docs/legal/reviews/dpa-review-v1.0-signoff.pdf` |
| Next review due | `[DATE + 12 months]` |

> **This template must not be sent to any customer before legal review sign-off is recorded above.**
