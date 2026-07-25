"""FND-074: CI must run vitest — the frontend regression tier needs a CI guarantee.

deploy.yml's `frontend` job ran only `npm ci` + `npm run build`, and ci.yml ran
pytest only, so every manifest entry pinned by `frontend/src/**/*.test.jsx`
(FND-021/022/023/029/031/052/053/054/073…) was enforced solely on developer
machines — a revert of any of them would merge green. The repo enforcement
model says "CI guarantees"; this pins that guarantee into the workflow YAML
itself, the same way FND-084 pins the ruff version.

Pinned properties:
- deploy.yml `frontend` job runs vitest AFTER `npm ci` and BEFORE the build,
  in the frontend directory, so a red frontend can never deploy.
- ci.yml has a job that runs vitest (after `npm ci`, frontend directory) and
  the workflow triggers on pull_request, so PR CI — not just deploy — gates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.regression, pytest.mark.unit]

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _run_lines(job: dict) -> list[str]:
    return [step.get("run", "") for step in job.get("steps", [])]


def _job_working_dirs(job: dict, step_idx: int) -> str:
    """Effective working-directory for a step: step-level wins over job default."""
    step = job["steps"][step_idx]
    if "working-directory" in step:
        return step["working-directory"]
    return job.get("defaults", {}).get("run", {}).get("working-directory", "")


def _find_step(job: dict, needle: str) -> int:
    for i, run in enumerate(_run_lines(job)):
        if needle in run:
            return i
    return -1


def test_deploy_frontend_job_runs_vitest_between_install_and_build():
    workflow = _load("deploy.yml")
    job = workflow["jobs"].get("frontend")
    assert job, "deploy.yml lost its frontend job — the deploy gate is gone (FND-074)"

    ci_idx = _find_step(job, "npm ci")
    vitest_idx = _find_step(job, "vitest run")
    build_idx = _find_step(job, "npm run build")

    assert vitest_idx != -1, (
        "deploy.yml frontend job does not run vitest — frontend-pinned FNDs "
        "(021/022/023/029/031/052/053/054/073…) have no deploy-time CI "
        "guarantee (FND-074)"
    )
    assert ci_idx != -1 and build_idx != -1, "frontend job lost npm ci / npm run build"
    assert ci_idx < vitest_idx < build_idx, (
        "vitest must run after `npm ci` (deps present) and before `npm run "
        "build` (fail fast, never ship a red frontend) — got order "
        f"npm ci={ci_idx}, vitest={vitest_idx}, build={build_idx}"
    )
    assert _job_working_dirs(job, vitest_idx) == "frontend", (
        "vitest step must execute in the frontend directory"
    )
    assert _find_step(job, "npm run lint") != -1, (
        "deploy.yml frontend job lost its eslint step — lint is a gate of "
        "record since FND-074"
    )


def _ci_vitest_job() -> tuple[str, dict] | None:
    workflow = _load("ci.yml")
    for name, job in workflow["jobs"].items():
        if _find_step(job, "vitest run") != -1:
            return name, job
    return None


def test_ci_yml_has_a_frontend_test_job_running_vitest():
    found = _ci_vitest_job()
    assert found, (
        "ci.yml has no job running vitest — PR CI does not gate on the "
        "frontend regression tier, only deploy would (FND-074)"
    )
    _, job = found
    ci_idx = _find_step(job, "npm ci")
    vitest_idx = _find_step(job, "vitest run")
    assert ci_idx != -1 and ci_idx < vitest_idx, (
        "ci.yml frontend job must `npm ci` before running vitest"
    )
    assert _job_working_dirs(job, vitest_idx) == "frontend", (
        "ci.yml vitest step must execute in the frontend directory"
    )
    assert _find_step(job, "npm run lint") != -1, (
        "ci.yml frontend job lost its eslint step — lint is a gate of record "
        "since FND-074"
    )


def test_ci_yml_gate_fires_on_pull_requests():
    """The finding's point is PR-time enforcement: merging a frontend-pin
    revert must go red BEFORE merge, not at deploy. `on:` parses as the
    boolean True under YAML 1.1, hence the odd key."""
    workflow = _load("ci.yml")
    triggers = workflow.get("on") or workflow.get(True) or {}
    assert "pull_request" in triggers, "ci.yml no longer triggers on pull_request"
