# STORY-365: Pen Test Readiness — Threat Model + Hardening Pass

**Status:** ready
**Screen/Area:** Security — backend, middleware, CI (Pack Epic 15)
**Ground truth:** TENANT_ISOLATION.md + test_pt009 concurrency proof exist; JWT
hardening plan doc exists. No STRIDE doc, no per-route authz probe matrix, rate
limiting / security headers / CORS state to be verified in code.

## Goal
A paid pen test finds real issues, not hygiene misses: STRIDE threat model,
hardening pass, and an automated route-authorization probe suite that doubles as
the INV-3 regression guard.

## Acceptance Criteria
- AC-1: STRIDE threat model doc for the three surfaces (sarofrontend.fly.dev,
  saro-backend.fly.dev, Supabase) at `docs/security/threat-model.md`.
- AC-2: Hardening implemented where missing: security headers middleware,
  rate limiting on auth + evaluate endpoints, CORS tightened to known origins.
- AC-3: Route inventory table (route → required role/persona → covering test).
- AC-4: Automated route-authorization suite in CI: unauthenticated + wrong-role
  probes for every registered route (auto-discovered from app.routes, so new
  unprotected routes fail the suite by default).
- AC-5: Pen-test scoping doc (in/out of scope, test accounts, RoE) at
  `docs/security/pentest-scope.md`.

## Edge Cases
- Public-by-design routes (health, docs, auth/login, trust/governance public
  endpoints) belong to an explicit allowlist with a comment per entry.

## Out of Scope
- Engaging a pen-test vendor (human).

## Traceability (filled at close)
| AC | Test(s) | Files |
|---|---|---|
