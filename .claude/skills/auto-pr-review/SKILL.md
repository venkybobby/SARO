---
name: auto-pr-review
description: Autonomous code review for SARO PRs. Triggered when reviewing a diff, PR, or before marking any implementation task complete. Checks correctness, security, compliance posture, and test coverage.
---

Perform a structured review of the current diff or named PR. Report findings by severity.

## Review Checklist

### Correctness
- Logic errors or off-by-one in scoring formulas (DIR, KS-test thresholds)
- Unhandled edge cases at API boundaries (null inputs, empty rule packs)
- Async/await correctness in FastAPI handlers
- Schema mismatches between Pydantic models and DB columns

### Security (OWASP Top 10 focus)
- SQL injection via raw queries — must use ORM or parameterised queries
- Missing input validation on user-controlled fields
- Secrets or credentials in code or logs
- Unprotected endpoints (missing auth dependency)
- Overly broad CORS or permissive headers

### SARO Non-Negotiables
- No calls to external AI models
- No writes to client systems
- No compliance certification language (check against COMPLIANCE_CLAIMS_MATRIX.md)
- Human-in-the-loop preserved for certification paths

### Test Coverage
- New logic has corresponding pytest test
- Happy path + at least one error/edge case covered
- No test that only tests the mock, not the logic

### Architecture
- No new files when editing an existing one would suffice
- No abstraction added for a single use case
- Conventional commit scope matches actual files changed

## Output Format

```
## PR Review — <branch or PR title>

### 🔴 Blockers (must fix before merge)
- <file>:<line> — <issue>

### 🟡 Warnings (should fix)
- <file>:<line> — <issue>

### 🟢 Passes
- Correctness: OK
- Security: OK
- Compliance language: OK
- Test coverage: OK

### Verdict: APPROVE | REQUEST CHANGES
```

If blockers exist, do NOT approve. List exact file:line references.
