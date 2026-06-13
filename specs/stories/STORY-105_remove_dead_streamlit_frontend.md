# STORY-105: Remove the dead Streamlit frontend and rewire deploy configs to React

**Status:** ready (⚠ destructive — deletes ~24 files + touches Railway/Docker/CI deploy config)
**Screen/Area:** frontend/ (Streamlit), Dockerfile.frontend, railway.toml, docker-compose.yml, CI

## Goal
The Streamlit UI in `frontend/` (`app.py` + `frontend/tabs/*.py` + `styles.py` + `frontend/requirements.txt`) has been superseded by the React/Vite app in `frontend/src/`. It is not imported by `main.py` or any backend router, but it is still wired into `Dockerfile.frontend`, `railway.toml` (Streamlit healthcheck `/_stcore/health`), `docker-compose.yml`, and CI installs its requirements. Remove the dead Streamlit code and ensure no deploy path still tries to run it.

## Context (file:line)
- Dead code: `frontend/app.py`, `frontend/tabs/*.py` (~23 files), `frontend/styles.py`, `frontend/requirements.txt:1` (`streamlit>=1.35.0`).
- `Dockerfile.frontend:20` — `CMD streamlit run frontend/app.py`; exposes 8501.
- `railway.toml:16-28` — `[services.frontend.build]` → `Dockerfile.frontend`; `healthcheckPath = "/_stcore/health"`.
- `docker-compose.yml:55-71` — `frontend` service → `Dockerfile.frontend`.
- `.github/workflows/ci.yml:74` — installs `frontend/requirements.txt`.
- Active React app: `frontend/src/`, `frontend/package.json`, `frontend/vite.config.js` (CI `npm run build`).

## Acceptance Criteria (Given/When/Then)
- **AC-1:** Given the Streamlit sources, When this story completes, Then `frontend/app.py`, `frontend/tabs/`, `frontend/styles.py`, and the Streamlit entry in `frontend/requirements.txt` are removed, and a repo-wide grep for `import streamlit` / `st.` Streamlit usage returns nothing under `frontend/` (excluding `.claude/worktrees`).
- **AC-2:** Given the deploy configs, When inspected after the change, Then no config references `Dockerfile.frontend`, the Streamlit `/_stcore/health` healthcheck, or `frontend/requirements.txt`: `Dockerfile.frontend` is deleted (or repointed to the Vite static build), `railway.toml`'s Streamlit `services.frontend` is removed/repointed, `docker-compose.yml`'s frontend service is removed/repointed, and CI no longer installs Streamlit deps.
- **AC-3:** Given the backend, When `pytest tests/ -q` and app startup run, Then nothing breaks (the Streamlit frontend was never imported by backend) and `GET /health` is unaffected.
- **AC-4:** Given the React app, When `npm run build` runs in `frontend/`, Then it still builds (the React app is the surviving frontend).

## Edge Cases
- Any backend code referencing `frontend/tabs/...` (none found, but `/story` must re-verify before deleting).
- STORY-102 may edit a "never calls external models" copy in `frontend/tabs/dashboard.py` — deleting it here removes that copy; sequence so the two don't collide.
- STORY-110 reasons about a Streamlit `_TAB_REGISTRY` for Reports — after this deletion, Reports access is purely a React concern (note for 110).

## Out of Scope
- Deleting the separate `veriaegis-landing/` Next.js dir (STORY-106).
- Any React feature change.

## Non-Functional Requirements
- Follow `.claude/skills/deploy-railway`: preserve health-check contract for surviving services, keep service topology coherent. Confirm before any push/deploy.

## Traceability
| AC | Test(s) | Files |
|---|---|---|
| AC-1 | `test_streamlit_sources_removed`, `test_no_streamlit_import_under_frontend` | frontend/ |
| AC-2 | `test_deploy_config_no_longer_references_streamlit` | railway.toml, docker-compose.yml, .github/workflows/ci.yml |
| AC-3 | full `pytest tests/ -m unit` + regression green after deletion; backend never imported frontend | tests/ |
| AC-4 | React app untouched (only frontend/src/* tracked under frontend/) | frontend/src/ |

**Status:** done. Removed `frontend/{app.py,styles.py,requirements.txt,__init__.py,tabs/*}`, `Dockerfile.frontend`, and 2 wholly-Streamlit tests (`test_frontend_login.py`, `test_s201_dashboard.py`). **Repointed** `test_sar006_rbac.py`'s 5 persona-tab tests from the deleted `frontend/app.py` to `persona_service.PERSONA_PERMISSIONS` (kept the backend RBAC tests). Rewired railway.toml (removed Streamlit frontend service), docker-compose.yml (removed frontend service), ci.yml (dropped Streamlit deps). Coverage rose to 80.50% (uncovered Streamlit lines left the denominator). Branch `story/STORY-105_remove_dead_streamlit_frontend` (stacked on 110). NOTE: deploy config edited locally only — not pushed/deployed.
