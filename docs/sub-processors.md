# SARO Sub-Processor Inventory

**Version:** 1.0 | **Last Updated:** May 2026 | **Owner:** Venky (Product Owner)

This document lists all third-party sub-processors that access, store, or process Personal Data on behalf of SARO customers.

---

## Active Sub-Processors

### Railway
| Field | Detail |
|-------|--------|
| **Purpose** | Application hosting — runs the SARO FastAPI backend and Streamlit frontend |
| **Data Access** | Application runtime environment; does not directly access database content |
| **Data Location** | United States (EU-West region available on request) |
| **Compliance** | SOC 2 Type II (confirm current status at railway.app/security) |
| **Data Retention** | Logs retained 30 days; no persistent data storage |
| **Contact** | security@railway.app |

### Supabase
| Field | Detail |
|-------|--------|
| **Purpose** | PostgreSQL database — stores audit records, user accounts, and all tenant data |
| **Data Access** | Full read/write access to structured data within the SARO schema |
| **Data Location** | United States (us-east-1); EU-West-1 available via project region selection |
| **Compliance** | SOC 2 Type II, GDPR-ready, ISO 27001 |
| **Data Retention** | Data retained per customer retention policy; purged on GDPR erasure request |
| **Encryption** | AES-256 at rest, TLS 1.3 in transit |
| **Contact** | privacy@supabase.io |

### Redis
| Field | Detail |
|-------|--------|
| **Purpose** | Session management — stores active user sessions and rate-limit state |
| **Data Access** | JWT session tokens only; no audit content or PII stored |
| **Data Location** | Co-located with application deployment |
| **Compliance** | Configured per deployment environment |
| **Data Retention** | Sessions expire after token TTL (configurable; default 24 hours) |
| **Encryption** | TLS in transit; encryption at rest configurable |

---

## Sub-Processor Change Notice

SARO will provide **30 days written notice** before adding or replacing sub-processors. Customers may object to new sub-processors within this notice period.

---

*Last reviewed: May 2026. Next review: May 2027.*
