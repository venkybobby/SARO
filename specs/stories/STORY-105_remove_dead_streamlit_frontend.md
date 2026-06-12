# STORY-105: Remove Dead Streamlit Frontend from SARO Repo (G-5)
Status: ready
Screen/Area: Repo Structure / `frontend/tabs/*.py`, `app.py`, `styles.py`, secondary `requirements.txt`

## Goal
22 Streamlit files coexist with the deployed React SPA (fly.toml + Dockerfile/nginx confirm React is production). Dead frontend code drifts, doubles the apparent attack/validation surface, and creates a "which frontend is real?" question in any source-code escrow review. Remove the Streamlit frontend with a recoverable archival point.

GRC mapping: ISO/IEC 42001 A.6.2.6 (configuration/change management); SOC 2 change-management evidence hygiene; escrow review readiness (Hale deal condition).

## Acceptance Criteria (Given/When/Then)
- AC-1: Given the current main branch, When the removal begins, Then a git tag (e.g., `archive/streamlit-frontend-2026-06`) is created first so the code is recoverable without keeping it live.
- AC-2: Given an import scan of the backend and CI scripts, When checked for references to the Streamlit modules (`frontend/tabs`, `app.py`, `styles.py`), Then zero live imports exist before deletion (verified, not assumed).
- AC-3: Given the deletion PR merges, When the repo is searched, Then no Streamlit files, no second `requirements.txt`, and no `streamlit` dependency remain, and CI is green.
- AC-4: Given ARCHITECTURE.md and README, When read post-merge, Then they state React SPA as the sole frontend with no Streamlit references outside the changelog/ADR.
- AC-5: Given the removal, When complete, Then an ADR records the decision, the archive tag, and the rationale (single-frontend source of truth).

## Edge Cases
- Shared utility modules imported by both Streamlit and backend → relocate to a neutral package before deletion.
- Demo scripts or runbooks invoking `streamlit run` → update or delete in the same PR.
- Open branches still touching Streamlit files → enumerate and notify before merge.

## Out of Scope
- Any React feature work; tab consolidation (STORY-112/113).

## Non-Functional Requirements
- Destructive action: confirm with product owner before the deletion commit (project rule). Standard FILES CHANGED summary.

## Traceability (filled at close by /story)
| AC | Test(s) | Files |
|----|---------|-------|
| | | |
