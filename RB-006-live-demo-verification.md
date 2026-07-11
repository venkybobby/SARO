# RB-006: Live Demo Verification Script

**Owner:** Venky R · **Time:** ~10 min · **Run:** T-24h before any external demo, and again T-1h.
**Supersedes:** RB-005 §4 "Technical Readiness" — that section referenced Koyeb, Neon, SHAP, and
Claude-generated report prose, all stale or contradicting current invariants (stack is frozen on
Fly.io + Supabase per PT-012, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); SARO's core
scoring never calls external AI models, see [`docs/COMPLIANCE_CLAIMS_MATRIX.md`](docs/COMPLIANCE_CLAIMS_MATRIX.md)).
RB-005 §§1–3, 5–6 (gap check, TRACE gate, claims audit, persona matching) remain in force.

---

## A. Backend reachability and demo token (the single most demo-critical check)

```bash
BASE=https://saro-backend.fly.dev   # canonical per fly.toml (app = 'saro-backend') and
                                     # docs/ARCHITECTURE.md — saro-platform.fly.dev, if it still
                                     # resolves, is a legacy mirror; do not use it for the demo.

curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/v1/demo/token
# 200 → proceed. 503 → SARO_DEMO_TENANT_ID unset: run scripts/seed_demo_tenant.py, set the secret, redeploy.

TOKEN=$(curl -s $BASE/api/v1/demo/token | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

## B. Every demo-tab endpoint returns 200 with the demo token

```bash
for EP in "/api/v1/risk/summary" \
          "/api/v1/risk/whats-changed" \
          "/api/v1/rules/drift-alerts" \
          "/api/v1/audits?limit=5" \
          "/api/v1/compliance-matrix/coverage" \
          "/api/v1/audits?limit=10&sort=desc" \
          "/api/v1/evf/validation-status" \
          "/api/v1/evf/qco/expiry-alerts?limit=20" \
          "/api/v1/compliance/readiness" \
          "/api/v1/risks"; do
  printf "%-45s " "$EP"
  curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" "$BASE$EP"
done
# All 200. Any 403 = STORY-412 whitelist violation. Any 500 = stop, fix before demo.
# This list is the exact endpoint census tests/regression/test_story_412_demo_tab_endpoint_census.py
# asserts in CI — if CI is green on that test, this section should already be green here too;
# a mismatch between the two means the deployed build is behind main.
```

## C. Seeded data is present, not just endpoints alive

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/audits?limit=5" | python3 -m json.tool | head -30
# Expect non-empty audit list from the demo corpus. Empty = seed/reset needed:
#   python cli.py demo reset --tenant <demo_tenant_id> --yes  (then re-ingest per operator runbook)
```

## D. UC-5 fires (STORY-411 live-fire, not merged-only)

```bash
# Find the UC-5 audit (off-allowlist modelId) and confirm ENV-MODEL-ALLOWLIST-1 appears in findings.
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/audits?limit=50" \
  | python3 -c "import sys,json; [print(a.get('id'), a.get('dataset_name')) for a in json.load(sys.stdin) if isinstance(a,dict)]" 2>/dev/null
# Then pull the trace detail for the UC-5 audit id and grep ENV-MODEL-ALLOWLIST-1.
# Absent = the marquee governance moment fails live. Do not demo UC-5 until this passes.
```

## E. Read-only enforcement (negative test)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"prompt":"x","raw_output":"y"}' "$BASE/api/v1/ingest"
# Expect 403. A 2xx here means the public demo token can WRITE — stop everything and fix.

curl -s -o /dev/null -w "%{http_code}\n" -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"completed":true}' "$BASE/api/v1/compliance/readiness/some-item-key"
# Expect 403. This is the one write button a demo visitor can actually click (the ComplianceHub
# readiness checklist) — STORY-412's independent reviewer found this reachable in round 1;
# it's fixed and regression-pinned, but re-verify live before every external demo.
```

## F. Environment hygiene on the deployed backend

```bash
fly ssh console -a saro-backend -C "printenv ANTHROPIC_API_KEY"   # MUST be empty — key presence activates Gate-3 external LLM calls
fly ssh console -a saro-backend -C "printenv SARO_DEMO_TENANT_ID" # MUST be set
fly ssh console -a saro-backend -C "printenv ALLOWED_ORIGINS"     # SHOULD be https://sarofrontend.fly.dev, not empty/*
```

## G. Credential rotation gate (from review finding #1 — blocks all external demos until done)

- [ ] `scripts/seed_demo_tenant.py` no longer contains a literal password; it reads `SARO_DEMO_SEED_PW` from env.
- [ ] The live demo tenant's `super_admin` password has been rotated away from the committed value.
- [ ] Confirm no other literal credentials: `git grep -iE "password\s*=\s*[\"'][^\"']{6,}"` returns only test fixtures.

## H. Browser pass (5 min, incognito)

- [ ] Open `https://sarofrontend.fly.dev/demo` → Dashboard loads with live numbers, no "sample" captions.
- [ ] Click every visible tab with DevTools Network open → zero 403s, zero red rows.
- [ ] Open one TRACE detail → renders findings including at least one UC-1..UC-5 exemplar.
- [ ] Hard-refresh mid-session → demo re-authenticates cleanly (token is state-held, not localStorage).
- [ ] Confirm no KPI tile reads "sample — not yet wired to live data" — STORY-413 removed this
      caption from the codebase; its live presence would mean the deployed build is stale.

**Gate:** all of A–H green, plus RB-005 §§1–3, before any external attendee joins.
