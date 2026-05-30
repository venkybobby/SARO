# SARO Gap Requirements Specification
**Version:** 1.0  
**Date:** 2026-05-27  
**Source spec:** SARO_ClaudeCode_Spec_v1.1.docx  
**Repo:** https://github.com/venkybobby/SARO  
**Production:** https://saro-production-2993.up.railway.app  

---

## How to Read This Document

Each gap entry has:
- **Status** — `BROKEN` (causes runtime error), `WRONG` (runs but returns bad data), `MISSING` (feature not built), `PARTIAL` (built but incomplete)
- **Severity** — `P0` crash/data-loss, `P1` feature broken, `P2` incomplete
- **Story** — which spec story owns it
- **Fix** — exact change required

Gaps are ordered by severity then story number.

---

## P0 — BROKEN: Runtime Crashes

### GAP-001 · `GET /api/v1/risk_dashboard` crashes with 500
**File:** `routers/fe_dashboard.py:119`  
**Story:** S-201 / S-203  
**Root cause:** Query references `Audit.source_model` and `ScanReport.risk_score`, neither of which exist as columns on those models.

```python
# CURRENT (broken)
db.query(Audit.source_model, ScanReport.risk_score)

# Audit.source_model → lives on AuditMetadata.source_model (separate table, 1:1 join)
# ScanReport.risk_score → column is named ScanReport.overall_risk_score
```

**Fix required:**
```python
# Option A — join AuditMetadata
db.query(AuditMetadata.source_model, ScanReport.overall_risk_score)
  .join(ScanReport, ScanReport.audit_id == Audit.id, isouter=True)
  .join(AuditMetadata, AuditMetadata.audit_id == Audit.id, isouter=True)

# Option B — use getattr fallback (already done in risk_dashboard.py but wrong default)
```

---

### GAP-002 · Daily HF sampler CI job fails on every run — 3 distinct causes
**File:** `.github/workflows/hf_sampler.yml`  
**Story:** S-002  

**Cause A — wrong argument name:**  
Workflow passes `--count 50`; script defines `--samples` (not `--count`).  
`argparse.parse_args()` raises `unrecognized arguments: --count` and exits 1.

**Cause B — unknown vertical "technology":**  
Workflow step "Sample Technology" passes `--vertical technology`.  
Script defines `choices=["healthcare", "finance", "legal", "general", "custom"]`.  
"technology" is not in choices → argparse exits 2 before any work is done.

**Cause C — undefined `--database-url` flag:**  
Workflow passes `--database-url "$DATABASE_URL"`.  
Script reads `DATABASE_URL` directly from the environment; it does not define a `--database-url` CLI flag.  
`parse_args()` exits 2 on the unrecognized flag.

**Fix required:**  
In `scripts/hf_sampler.py`, add the `--database-url` argument and alias `--count` to `--samples`, and add "technology" to `_VERTICAL_DATASETS`:
```python
# Add to parser
parser.add_argument("--count", dest="samples", type=int, default=100)
parser.add_argument("--database-url", default=None)

# Set DATABASE_URL if --database-url was passed
if args.database_url:
    os.environ["DATABASE_URL"] = args.database_url

# Add to _VERTICAL_DATASETS
"technology": {
    "dataset": "allenai/WildChat-1M",
    "prompt_col": "conversation",
    "output_col": "conversation",
    "source_model": "unknown",
},
```

---

### GAP-003 · Daily HF sampler triggers wrong URL — processor endpoint never fires
**File:** `.github/workflows/hf_sampler.yml` (Trigger processor step)  
**Story:** S-002 / S-003  

Workflow calls:
```
https://saro-platform.fly.dev/api/v1/hf-processor/run
```

Two errors:
1. **Wrong domain:** App runs on Railway (`https://saro-production-2993.up.railway.app`), not `saro-platform.fly.dev` (Fly.io is not deployed — see GAP-011).
2. **Wrong path:** Router is mounted at `/api/v1/hf/process`, not `/api/v1/hf-processor/run`.

**Fix required:**
```yaml
env:
  SARO_URL: ${{ secrets.SARO_RAILWAY_URL }}   # set to https://saro-production-2993.up.railway.app
run: |
  curl -X POST \
    "$SARO_URL/api/v1/hf/process" \           # correct path
    -H "Authorization: Bearer $SARO_BEARER" \
    -w "\nHTTP %{http_code}\n"
```

---

### GAP-004 · S-205 demo read-only guard never fires — any demo user can write
**File:** `routers/demo.py:177`, `auth.py:155`  
**Story:** S-205  

`routers/demo.py` issues a JWT with `"read_only": True` in the payload.  
The `require_write_access` dependency checks `getattr(current_user, "read_only", False)`.  
But `get_current_user` (in `auth.py`) returns a SQLAlchemy `User` row — it does **not** copy JWT claims onto the object. The `User` model has no `read_only` column.  
Result: `getattr(current_user, "read_only", False)` always returns `False`; demo users can call every write endpoint.

**Fix required:**
```python
# auth.py — attach JWT claims to user object after loading from DB
user = db.get(User, user_id)
...
user.read_only = payload.get("read_only", False)   # transient attribute, not persisted
return user
```

---

## P0 — WRONG: Silent Data Corruption

### GAP-005 · `GET /api/v1/risk/summary`, `/risk/vendors`, `/risk/whats-changed` always return null scores
**File:** `routers/risk_dashboard.py`  
**Story:** S-201  

`_get_audit_records()` uses:
```python
"risk_score": getattr(report, "risk_score", None)
"source_model": getattr(audit, "source_model", None)
```

Both attributes don't exist on the model objects (column is `overall_risk_score`; `source_model` is on `AuditMetadata`). `getattr` with a default silently returns `None` instead of crashing. The board-level risk dashboard always shows 0 vendors, null scores, and null RAG status — regardless of how many real audits exist.

**Fix required:** Same as GAP-001 — join `AuditMetadata`, rename `risk_score` → `overall_risk_score`.

---

### GAP-006 · `GET /api/v1/compliance-matrix/coverage` response missing `namespace` and `window_days` fields
**File:** `routers/fe_dashboard.py` (`get_compliance_matrix`)  
**Story:** S-203  

Spec requires:
```json
{
  "frameworks": [
    { "name": "NIST AI RMF", "rules_total": 22, "rules_triggered": 18,
      "coverage_pct": 81.8, "namespace": "nist_ai_rmf" }
  ],
  "window_days": 7,
  "computed_at": "..."
}
```

Current response omits `namespace` (per-framework) and `window_days` (top-level). The `RegCoverage.jsx` frontend component likely relies on these for display.

**Fix required:** Add `namespace` mapping in `fe_dashboard.py` and return `window_days` in the response dict.

---

## P1 — BROKEN: Features Not Working

### GAP-007 · S-103 SDK Snippet — only Python, wrong response format, field names inconsistent with spec
**File:** `routers/ingest.py` (`get_sdk_snippet`)  
**Story:** S-103  

Spec acceptance criteria:
- `GET /api/v1/sdk/snippet?lang=python` → 200 `text/plain` (no JSON wrapper, no Markdown fences)
- `GET /api/v1/sdk/snippet?lang=javascript` → 200 `text/plain`
- `GET /api/v1/sdk/snippet?lang=curl` → 200 `text/plain`
- `GET /api/v1/sdk/snippet?lang=ruby` → 400

Current implementation:
- Ignores `?lang=` query parameter entirely
- Always returns a JSON object `{"language": "python", "snippet": "...", ...}` — not `text/plain`
- No JavaScript or curl snippets
- No 400 for unsupported languages

**Fix required:**
```python
@router.get("/sdk/snippet", response_class=PlainTextResponse)
def get_sdk_snippet(
    lang: str = Query(default="python"),
    current_user: Annotated[User, Depends(get_current_user)] = ...,
) -> str:
    if lang not in ("python", "javascript", "curl"):
        raise HTTPException(status_code=400, detail="lang must be python, javascript, or curl")
    # Return PlainTextResponse with snippet for requested language
```

---

### GAP-008 · S-202 TRACE view — Alex Rivera authorship hard gate not enforced
**File:** `routers/trace_view.py`, `frontend/src/pages/Dashboard.jsx`  
**Story:** S-202  

Spec: *"S-202 must not be shown in any enterprise demo until Alex Rivera has set the `model_version` field on the `EnhancedTrace` record for the demo tenant audits."*

Backend correctly reads `EnhancedTrace.model_version` and returns it in the trace response. However:
1. No ownership/authorship check that it was specifically set by Alex Rivera (e.g., via a `set_by` field)
2. No frontend component enforces the "Not yet available — awaiting ML Lead review" gate state
3. `EnhancedTrace` rows are created with `model_version = None` — any populated `model_version` string bypasses the gate, even if it wasn't set by the authorized reviewer

**Fix required:**
- Add `model_version_set_by` field to `EnhancedTrace` or use a separate approval flag
- Frontend `TRACE` panel: if `model_version` is null or gate flag is false, render "Not yet available — awaiting ML Lead review" placeholder instead of the chain-of-thought

---

### GAP-009 · S-201 Dashboard vertical switcher disconnected from backend
**File:** `frontend/src/pages/Dashboard.jsx`, backend routers  
**Story:** S-201  

Dashboard shows vertical options: `["finance", "healthcare", "technology", "government"]`.  
Neither `GET /api/v1/compliance-matrix/coverage` nor `GET /api/v1/risk_dashboard` nor `GET /api/v1/audits` accept a `?vertical=` filter parameter.  
Switching verticals on the dashboard has no effect on the data returned.  
Additionally, "technology" is not a valid backend vertical (see GAP-002-B).

**Fix required:**
- Add `vertical` query param to `GET /api/v1/audits`, `GET /api/v1/compliance-matrix/coverage`, and `GET /api/v1/risk_dashboard`
- Filter queries by `AuditMetadata.ingestion_method` or add a `vertical` column to `Audit`
- Remove "technology" from the frontend vertical list or add it to backend enum

---

### GAP-010 · S-301/S-302 CI/CD pipeline deploys to Fly.io — app runs on Railway
**Files:** `.github/workflows/deploy.yml`, `fly.toml`  
**Story:** S-301, S-302  

The spec story S-301 describes a Fly.io deployment. The app is actually live on Railway. `deploy.yml` runs `flyctl deploy` and health-checks `https://saro-platform.fly.dev/health`.

Current state: Either the deploy job silently succeeds to a dead Fly.io app while Railway is updated separately (out of band), or CI never actually deploys production.

**Fix required — two paths, choose one:**

**Path A (stay on Railway):**
- Update `deploy.yml` to use Railway CLI (`railway up`) instead of `flyctl`
- Health-check `https://saro-production-2993.up.railway.app/health`
- Remove `fly.toml` or mark it archived

**Path B (migrate to Fly.io per spec):**
- Complete `fly.toml` configuration (currently missing `[env] DATABASE_URL`, health check path)
- Ensure `FLY_API_TOKEN` secret is set in GitHub
- Migrate Neon PostgreSQL connection string to Fly.io secrets
- Update `SARO_API_URL` env var on Fly.io

---

## P1 — MISSING: Stories Not Implemented

### GAP-011 · S-104 — story not defined in spec, not implemented
**Story:** S-104  

S-104 appears in the table of contents ("Epic 1 — Vendor Ingest Pipeline (S-101 to S-104)") but has no story body in the spec document. No corresponding implementation exists in the codebase. Before any work can start, the product owner must define S-104.

**Action:** Product owner (Venky) to write the S-104 story body. Mark as blocked until defined.

---

### GAP-012 · S-000 Demo Seed Script — targets Fly.io, not Railway
**File:** `scripts/seed_demo_tenant.py`  
**Story:** S-000  

Script's default `--saro-url` is `https://saro-platform.fly.dev`. Since the app runs on Railway, the seed script will POST audit data to a nonexistent or wrong server.

**Fix required:**
```python
# Change default URL
parser.add_argument("--saro-url", default="https://saro-production-2993.up.railway.app")
```

---

### GAP-013 · S-303 — Integration test `test_s000_seed.py` missing
**Story:** S-303  
**Spec says:** `tests/test_s000_seed.py` must contain `test_idempotent_tenant_creation` and `test_verify_dashboard`.  
File does not exist in the repo.

---

## P2 — PARTIAL: Incomplete Implementations

### GAP-014 · S-103 snippet field names don't match actual ingest API contract
**File:** `routers/ingest.py` `IngestRequest` schema vs SDK snippet  
**Story:** S-103  

The spec's S-103 snippet uses `prompt_text` / `raw_output_text` / `ingestion_method` as JSON field names. The actual `IngestRequest` schema uses `prompt` / `raw_output` (no `_text` suffix). The Python snippet generated by the current implementation correctly uses `prompt` and `raw_output`, but the JavaScript and curl snippets (when added per GAP-007) must use the same names.

Also: the spec snippet pre-fills `"source_model": "openai"` as a placeholder. The current snippet pre-fills `"source_model": source_model` from function arg. The spec requires the tenant's model list to drive the default, not a hardcoded string.

---

### GAP-015 · S-302 deploy.yml — type check step always passes even with errors
**File:** `.github/workflows/deploy.yml`  
**Story:** S-302  

```yaml
- name: Type check (mypy)
  run: mypy . --ignore-missing-imports
  continue-on-error: true       # ← silences all mypy failures
```

The spec does not specify `continue-on-error: true` for mypy. With this setting, type errors never block CI. At minimum, the team should decide whether this is intentional or whether mypy is meant to be a gate.

---

### GAP-016 · S-204 Remediation — `regulation_ref` field absent from tenant-wide list
**File:** `routers/remediation.py`  
**Story:** S-204  

Spec requires each item in `GET /api/v1/remediation` to include:
```json
{ "regulation_ref": "NIST-MEASURE-2.5" }
```

The `AuditTrace` model has no `regulation_ref` column and the router doesn't compute or return this field. Operators can't see which regulation triggered a finding.

---

### GAP-017 · React frontend not wired to a build/deploy pipeline
**Files:** `frontend/src/`, no `package.json` at repo root, no Vercel config  
**Story:** S-201  

The React/JSX components exist (`Dashboard.jsx`, `RegCoverage.jsx`, etc.) but there is no:
- `package.json` / `node_modules` at the repo root or in `frontend/src/`
- `vite.config.js` or `webpack.config.js`
- Vercel deployment config (`vercel.json`)
- Build step in `deploy.yml`

The frontend code exists but is never compiled or served. The production app at the Railway URL presumably still serves the Streamlit frontend (`frontend/app.py`), not the React components.

**Fix required:**
- Add `package.json` with React/Vite dependencies to `frontend/` directory
- Add build step to `deploy.yml`: `npm ci && npm run build`
- Configure Vercel project or serve from Railway as static files
- Set `REACT_APP_SARO_API_URL` build-time env var

---

## Summary Table

| Gap | Severity | Story | Status | Component |
|-----|----------|-------|--------|-----------|
| GAP-001 | P0 BROKEN | S-201/203 | Runtime 500 | `fe_dashboard.py` — wrong column names |
| GAP-002 | P0 BROKEN | S-002 | CI never runs | `hf_sampler.yml` — `--count`, `--database-url`, `technology` vertical all wrong |
| GAP-003 | P0 BROKEN | S-002/003 | Processor never triggers | `hf_sampler.yml` — wrong domain + wrong endpoint path |
| GAP-004 | P0 BROKEN | S-205 | Security hole | `demo.py` read-only guard — JWT claim not propagated to User object |
| GAP-005 | P0 WRONG | S-201 | Null data | `risk_dashboard.py` — silent `getattr` fallback on wrong column names |
| GAP-006 | P1 WRONG | S-203 | Missing fields | Coverage response missing `namespace` + `window_days` |
| GAP-007 | P1 BROKEN | S-103 | Feature missing | SDK snippet — no `?lang=`, no JS/curl, wrong response format |
| GAP-008 | P1 BROKEN | S-202 | Gate not enforced | TRACE view — Alex Rivera authorship hard gate missing |
| GAP-009 | P1 BROKEN | S-201 | UX broken | Vertical switcher has no backend effect |
| GAP-010 | P1 BROKEN | S-301/302 | Deploy broken | CI deploys to Fly.io; app runs on Railway |
| GAP-011 | P1 MISSING | S-104 | Story undefined | S-104 has no spec body — cannot be implemented |
| GAP-012 | P1 MISSING | S-000 | Wrong URL | Seed script targets Fly.io |
| GAP-013 | P1 MISSING | S-303 | Test absent | `test_s000_seed.py` does not exist |
| GAP-014 | P2 PARTIAL | S-103 | Inconsistency | Snippet field names differ between spec and API |
| GAP-015 | P2 PARTIAL | S-302 | CI too lenient | mypy runs with `continue-on-error: true` |
| GAP-016 | P2 PARTIAL | S-204 | Missing field | `regulation_ref` absent from remediation list |
| GAP-017 | P2 MISSING | S-201 | Not shipped | React frontend has no build/deploy pipeline |

---

## Story-level Status

| Story | Title | Status | Blocker |
|-------|-------|--------|---------|
| S-000 | Demo Seed Script | PARTIAL | Wrong URL (GAP-012); test missing (GAP-013) |
| S-001 | HF Sample Queue | COMPLETE | — |
| S-002 | HF Sampler Script | BROKEN | CI workflow args wrong (GAP-002, GAP-003) |
| S-003 | HF Processor Router | PARTIAL | Processor URL wrong in workflow (GAP-003) |
| S-101 | Universal Ingest API | COMPLETE | — |
| S-102 | Audit Status Polling | COMPLETE | — |
| S-103 | SDK Snippet | PARTIAL | Wrong format, missing languages (GAP-007, GAP-014) |
| S-104 | (undefined) | BLOCKED | Story body missing from spec (GAP-011) |
| S-201 | E2E Dashboard | PARTIAL | Column bugs (GAP-001/005), vertical filter missing (GAP-009), React not deployed (GAP-017) |
| S-202 | TRACE View | PARTIAL | Authorship gate not enforced (GAP-008) |
| S-203 | Compliance Heatmap | PARTIAL | Missing response fields (GAP-006) |
| S-204 | Remediation Workflow | PARTIAL | `regulation_ref` missing (GAP-016) |
| S-205 | Demo Route | BROKEN | Read-only guard never fires (GAP-004) |
| S-301 | Platform Deployment | BROKEN | Wrong platform — fly.io vs Railway (GAP-010) |
| S-302 | CI/CD Pipeline | PARTIAL | Deploys to wrong platform; mypy not gating (GAP-010, GAP-015) |
| S-303 | Integration Tests | PARTIAL | S-000 test file missing (GAP-013) |

---

## Recommended Fix Order

1. **GAP-004** — demo users can write data (security)
2. **GAP-001 + GAP-005** — fix column name bugs in `fe_dashboard.py` and `risk_dashboard.py` (runtime crashes + silent nulls)
3. **GAP-010** — decide Railway vs Fly.io, fix CI/CD to match (blocks every deploy)
4. **GAP-002 + GAP-003** — fix hf_sampler.yml workflow args and URL (daily data pipeline dead)
5. **GAP-007** — complete SDK snippet (customer-facing, in client demos)
6. **GAP-009 + GAP-006** — vertical filter + coverage response fields (dashboard shows wrong data)
7. **GAP-017** — wire React frontend to a build/deploy pipeline (otherwise it exists only as dead code)
8. **GAP-008** — enforce TRACE authorship gate (contractual requirement)
9. **GAP-012 + GAP-013** — fix seed script URL, add missing test file
10. **GAP-011** — get S-104 story defined by product owner
11. **GAP-014 + GAP-015 + GAP-016** — field name consistency, mypy gate, regulation_ref field

---

*Generated by code review against spec v1.1 and repo HEAD. No fixes applied — this is a read-only gap analysis.*
