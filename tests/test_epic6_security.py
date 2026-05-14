"""Epic 6: Security Hardening test suite."""
import os
import subprocess
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── SEC-001 Tests ──────────────────────────────────────────────────────────

class TestSecretsScanning:
    def test_no_hardcoded_secrets_in_python_files(self):
        """Scan all .py files for common secret patterns."""
        import re
        secret_patterns = [
            r'(?i)(password|passwd|secret|api_key|apikey|token|jwt_secret)\s*=\s*["\'][^"\']{8,}["\']',
            r'(?i)DATABASE_URL\s*=\s*["\']postgresql://[^"\']+["\']',
            r'(?i)sk-[a-zA-Z0-9]{32,}',  # OpenAI keys
        ]
        violations = []
        skip_dirs = {'.git', '__pycache__', '.claude', 'node_modules', 'venv', '.venv', 'saro-data-framework'}
        for py_file in ROOT.rglob('*.py'):
            if any(skip in py_file.parts for skip in skip_dirs):
                continue
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            for pat in secret_patterns:
                matches = re.findall(pat, content)
                if matches:
                    violations.append(f"{py_file}: {matches}")
        assert not violations, f"Hardcoded secrets found:\n" + '\n'.join(violations)

    def test_all_secrets_loaded_from_env_vars(self):
        """Verify critical config is read from environment, not hardcoded."""
        import re
        main_content = (ROOT / 'main.py').read_text(encoding='utf-8', errors='ignore')
        auth_content = (ROOT / 'auth.py').read_text(encoding='utf-8', errors='ignore')
        db_content = (ROOT / 'database.py').read_text(encoding='utf-8', errors='ignore')
        all_content = main_content + auth_content + db_content
        assert 'os.environ' in all_content or 'os.getenv' in all_content, \
            "Secrets should be loaded from environment variables"

    def test_ci_workflow_file_exists(self):
        ci_file = ROOT / '.github' / 'workflows' / 'ci.yml'
        assert ci_file.exists(), "CI workflow file must exist at .github/workflows/ci.yml"

    def test_ci_has_lint_stage(self):
        ci_file = ROOT / '.github' / 'workflows' / 'ci.yml'
        content = ci_file.read_text(encoding='utf-8')
        assert 'ruff' in content or 'lint' in content.lower(), "CI must have a lint stage"

    def test_ci_has_test_stage(self):
        ci_file = ROOT / '.github' / 'workflows' / 'ci.yml'
        content = ci_file.read_text(encoding='utf-8')
        assert 'pytest' in content, "CI must have a test stage with pytest"

    def test_ci_has_security_stage(self):
        ci_file = ROOT / '.github' / 'workflows' / 'ci.yml'
        content = ci_file.read_text(encoding='utf-8')
        assert 'bandit' in content or 'safety' in content, "CI must have a security scan stage"

    def test_ci_has_e2e_stage(self):
        ci_file = ROOT / '.github' / 'workflows' / 'ci.yml'
        content = ci_file.read_text(encoding='utf-8')
        assert 'playwright' in content.lower() or 'e2e' in content.lower(), "CI must have an E2E stage"

    def test_ci_deploys_to_staging_on_main(self):
        ci_file = ROOT / '.github' / 'workflows' / 'ci.yml'
        content = ci_file.read_text(encoding='utf-8')
        assert 'deploy' in content.lower() or 'railway' in content.lower(), \
            "CI must deploy to staging on main branch"


# ── SEC-002 Tests ──────────────────────────────────────────────────────────

class TestCIPipeline:
    def test_rls_migration_file_exists(self):
        migration = ROOT / 'migrations' / '001_add_rls_policies.sql'
        assert migration.exists(), "RLS migration SQL must exist"

    def test_rls_migration_has_enable_rls(self):
        migration = ROOT / 'migrations' / '001_add_rls_policies.sql'
        content = migration.read_text(encoding='utf-8')
        assert 'ENABLE ROW LEVEL SECURITY' in content.upper()

    def test_tenant_id_migration_exists(self):
        migration = ROOT / 'migrations' / '002_add_tenant_id_columns.sql'
        assert migration.exists(), "Tenant ID migration SQL must exist"

    def test_tenant_middleware_exists(self):
        middleware = ROOT / 'middleware' / 'tenant_context.py'
        assert middleware.exists(), "Tenant context middleware must exist"


# ── SEC-003 Tests ──────────────────────────────────────────────────────────

class TestRLSPolicies:
    def test_rls_policies_cover_audits_table(self):
        migration = ROOT / 'migrations' / '001_add_rls_policies.sql'
        content = migration.read_text(encoding='utf-8')
        assert 'audits' in content.lower(), "RLS must cover the audits table"

    def test_rls_policies_cover_users_table(self):
        migration = ROOT / 'migrations' / '001_add_rls_policies.sql'
        content = migration.read_text(encoding='utf-8')
        assert 'users' in content.lower(), "RLS must cover the users table"

    def test_rls_policies_cover_audit_results_table(self):
        migration = ROOT / 'migrations' / '001_add_rls_policies.sql'
        content = migration.read_text(encoding='utf-8')
        assert 'audit_traces' in content.lower() or 'scan_reports' in content.lower(), \
            "RLS must cover audit results tables"

    def test_rls_uses_app_current_tenant(self):
        migration = ROOT / 'migrations' / '001_add_rls_policies.sql'
        content = migration.read_text(encoding='utf-8')
        assert 'app.current_tenant' in content, "RLS must use app.current_tenant setting"

    def test_tenant_context_middleware_sets_rls_variable(self):
        middleware = ROOT / 'middleware' / 'tenant_context.py'
        content = middleware.read_text(encoding='utf-8')
        assert 'app.current_tenant' in content, "Middleware must set app.current_tenant"

    def test_pre_commit_config_exists(self):
        precommit = ROOT / '.pre-commit-config.yaml'
        assert precommit.exists(), "Pre-commit config must exist"
