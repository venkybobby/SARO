"""
SAR-003: Demo Seed Infrastructure — unit tests.

1. test_fly_toml_has_min_machines_running_1
2. test_fly_toml_has_health_check_path
3. test_seed_script_defines_all_four_verticals
4. test_seed_script_has_env_demo_write
5. test_seed_demo_workflow_exists
6. test_deploy_workflow_has_fly_deploy
7. test_seed_script_idempotent_on_existing_tenant
"""
from __future__ import annotations

import os
import pathlib

_REPO_ROOT = pathlib.Path(__file__).parent.parent


class TestFlyToml:
    def _read_fly_toml(self) -> str:
        return (_REPO_ROOT / "fly.toml").read_text(encoding="utf-8")

    def test_fly_toml_has_min_machines_running_1(self):
        content = self._read_fly_toml()
        assert "min_machines_running = 1" in content, (
            "fly.toml must contain 'min_machines_running = 1' to prevent cold starts"
        )

    def test_fly_toml_has_health_check_path(self):
        content = self._read_fly_toml()
        assert "/health" in content, (
            "fly.toml must reference '/health' as the health check path"
        )


class TestSeedScriptContent:
    def _read_seed_script(self) -> str:
        return (_REPO_ROOT / "scripts" / "seed_demo_tenant.py").read_text(encoding="utf-8")

    def test_seed_script_defines_all_four_verticals(self):
        content = self._read_seed_script()
        for vertical in ("finance", "healthcare", "technology", "government"):
            assert vertical in content, (
                f"seed_demo_tenant.py must reference vertical '{vertical}'"
            )

    def test_seed_script_has_env_demo_write(self):
        content = self._read_seed_script()
        assert ".env.demo" in content, (
            "seed_demo_tenant.py must write credentials to .env.demo"
        )
        assert "SARO_DEMO_TENANT_ID" in content, (
            "seed_demo_tenant.py must write SARO_DEMO_TENANT_ID to .env.demo"
        )
        assert "SARO_DEMO_TOKEN" in content, (
            "seed_demo_tenant.py must write SARO_DEMO_TOKEN to .env.demo"
        )
        assert "SARO_DEMO_URL" in content, (
            "seed_demo_tenant.py must write SARO_DEMO_URL to .env.demo"
        )

    def test_seed_script_idempotent_on_existing_tenant(self):
        """
        Verify idempotency guard: the seed script must handle an already-seeded
        state without re-inserting all 800 records. We check this by reading the
        source — it must contain either 'ON CONFLICT' (SQL idempotency) or an
        explicit >= 800 skip guard (Python-level idempotency).
        """
        content = self._read_seed_script()
        has_conflict_guard = "ON CONFLICT" in content
        has_python_skip_guard = ">= 800" in content or "skipped" in content
        assert has_conflict_guard or has_python_skip_guard, (
            "seed_demo_tenant.py must be idempotent: use ON CONFLICT or a "
            "Python-level guard that skips re-seeding when >= 800 records exist"
        )


class TestWorkflows:
    def test_seed_demo_workflow_exists(self):
        workflow_path = _REPO_ROOT / ".github" / "workflows" / "seed-refresh.yml"
        assert workflow_path.exists(), (
            f"Weekly seed refresh workflow not found at {workflow_path}"
        )

    def test_deploy_workflow_has_fly_deploy(self):
        deploy_path = _REPO_ROOT / ".github" / "workflows" / "deploy.yml"
        content = deploy_path.read_text(encoding="utf-8")
        assert "flyctl deploy" in content, (
            "deploy.yml must contain 'flyctl deploy' step"
        )


class TestSeedPayloads:
    def test_seed_payloads_800_records_total(self):
        """Each vertical must have exactly 200 records — 800 total."""
        import sys
        sys.path.insert(0, str(_REPO_ROOT))
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
        from scripts.seed_demo_tenant import SEED_PAYLOADS, RECORDS_PER_VERTICAL, VERTICALS

        assert set(SEED_PAYLOADS.keys()) == set(VERTICALS)
        for vertical in VERTICALS:
            count = len(SEED_PAYLOADS[vertical])
            assert count == RECORDS_PER_VERTICAL, (
                f"vertical '{vertical}' has {count} records; expected {RECORDS_PER_VERTICAL}"
            )
        total = sum(len(v) for v in SEED_PAYLOADS.values())
        assert total == 800, f"Expected 800 total seed records, got {total}"

    def test_seed_payloads_risk_distribution(self):
        """Per vertical: 40 CRITICAL, 60 HIGH, 60 MEDIUM, 40 LOW."""
        import sys
        sys.path.insert(0, str(_REPO_ROOT))
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
        from scripts.seed_demo_tenant import SEED_PAYLOADS, VERTICALS

        for vertical in VERTICALS:
            from collections import Counter
            dist = Counter(p["risk_level"] for p in SEED_PAYLOADS[vertical])
            assert dist["CRITICAL"] == 40, (
                f"{vertical}: expected 40 CRITICAL, got {dist['CRITICAL']}"
            )
            assert dist["HIGH"] == 60, (
                f"{vertical}: expected 60 HIGH, got {dist['HIGH']}"
            )
            assert dist["MEDIUM"] == 60, (
                f"{vertical}: expected 60 MEDIUM, got {dist['MEDIUM']}"
            )
            assert dist["LOW"] == 40, (
                f"{vertical}: expected 40 LOW, got {dist['LOW']}"
            )
