---
name: security-audit
description: Automated security audit for SARO code changes. Triggered before any PR merge, when adding new endpoints, modifying auth.py, or on scheduled security runs. Checks OWASP Top 10, PII exposure, and SARO-specific attack surfaces.
---

Run a structured security audit on the specified files or current diff. Flag all findings before merge.

## Automated Checks (run these commands)

```bash
# Dependency vulnerabilities
pip-audit --requirement requirements.txt --format json

# Secrets in code
grep -rn "password\s*=\s*['\"].\+['\"]" --include="*.py" .
grep -rn "api_key\s*=\s*['\"].\+['\"]" --include="*.py" .

# SQL injection candidates (raw string queries)
grep -rn "execute\s*(" --include="*.py" .

# Hardcoded tokens
grep -rn "Bearer [A-Za-z0-9\-_]" --include="*.py" .
```

## Manual Review — OWASP Top 10 for FastAPI

| Risk | Check |
|---|---|
| A01 Broken Access Control | Every router endpoint has auth dependency injected |
| A02 Cryptographic Failures | No MD5/SHA1 for security purposes; TRACE uses SHA-256 |
| A03 Injection | All DB queries use SQLAlchemy ORM or parameterised statements |
| A04 Insecure Design | Audit endpoints are read-only; no client-write paths exist |
| A05 Security Misconfiguration | CORS origins not set to `*`; debug mode off in prod |
| A06 Vulnerable Components | `pip-audit` clean |
| A07 Auth Failures | JWT expiry enforced; no token in query params or logs |
| A08 Integrity Failures | TRACE chain uses SHA-256 hash chaining |
| A09 Logging Failures | No PII (email, name, IP) in structured logs |
| A10 SSRF | No user-controlled URLs fetched by the backend |

## SARO-Specific Attack Surfaces

- **Scan endpoint** (`POST /api/v1/scan`): validate `prompt` and `raw_output` size limits; reject > 100KB inputs
- **Rule packs**: validate JSON schema on load; reject unknown keys
- **TRACE export**: ensure hash chain cannot be overwritten via API
- **Auth tokens**: confirm refresh token rotation is enforced

## PII Check
Scan all API response schemas for fields that could expose PII:
- No raw email addresses in scan results
- No IP addresses in TRACE records
- Client IDs must be UUIDs, not names

## Output Format

```
## Security Audit — <scope>

### Critical
- <file>:<line> — <vulnerability> — <fix>

### High
- ...

### Medium / Informational
- ...

### pip-audit result: CLEAN | <N vulnerabilities found>

### Verdict: PASS | FAIL
```

FAIL blocks merge. Fix all Critical and High findings first.
