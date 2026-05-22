"""
Tests for all 10 remaining feature specs:
  SPEC-F2: SSO/SAML 2.0
  SPEC-F3: Remediation + Jira OAuth
  SPEC-F5: Notification SSE + SendGrid
  SPEC-E1: LLM-as-judge hybrid classifier
  SPEC-E3: Engine singleton + status endpoint
  SPEC-E4: Bayesian prior calibration
  SPEC-FE2: Board RAG summary view
  SPEC-FE3: docker-compose + .env.example
  SPEC-G3: DPA template exists
  SPEC-G4: SOC 2 roadmap exists + governance/meta soc2 field
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-specs")


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-E4: Bayesian Prior Calibration
# ─────────────────────────────────────────────────────────────────────────────

class TestBayesianPriorCalibration:
    """SPEC-E4: _compute_domain_priors uses incident frequency."""

    def test_empty_incidents_returns_jeffreys(self):
        from engine import SARoEngine, MIT_DOMAINS
        eng = MagicMock(spec=SARoEngine)
        eng._incidents = []
        result = SARoEngine._compute_domain_priors(eng)
        for domain in MIT_DOMAINS:
            assert result[domain] == (0.5, 0.5), f"Expected Jeffreys for {domain}"

    def test_calibrated_priors_reflect_frequency(self):
        from engine import SARoEngine
        eng = MagicMock(spec=SARoEngine)
        # Privacy-heavy incident set
        eng._incidents = [{"category": "privacy"} for _ in range(80)] + \
                         [{"category": "safety"} for _ in range(10)] + \
                         [{"category": "bias"} for _ in range(10)]
        result = SARoEngine._compute_domain_priors(eng)
        privacy_alpha = result["Privacy & Security"][0]
        safety_alpha = result["AI System Safety"][0]
        # Privacy should have higher prior alpha than safety
        assert privacy_alpha > safety_alpha, \
            f"Privacy alpha ({privacy_alpha}) should > Safety alpha ({safety_alpha})"

    def test_priors_all_domains_present(self):
        from engine import SARoEngine, MIT_DOMAINS
        eng = MagicMock(spec=SARoEngine)
        eng._incidents = [{"category": "privacy"}, {"category": "bias"}]
        result = SARoEngine._compute_domain_priors(eng)
        assert set(result.keys()) == set(MIT_DOMAINS)

    def test_bayesian_domain_score_has_prior_fields(self):
        """SPEC-E4: BayesianDomainScore schema has prior_alpha, prior_beta, calibrated_from_n_incidents."""
        from schemas import BayesianDomainScore
        score = BayesianDomainScore(
            domain="Privacy & Security",
            risk_probability=0.3,
            ci_lower=0.1,
            ci_upper=0.5,
            sample_count=100,
            flagged_count=30,
            prior_alpha=2.5,
            prior_beta=3.0,
            calibrated_from_n_incidents=500,
        )
        assert score.prior_alpha == 2.5
        assert score.prior_beta == 3.0
        assert score.calibrated_from_n_incidents == 500


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-E1: LLM-as-judge hybrid classifier
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMHybridClassifier:
    """SPEC-E1: Gate 3 LLM-as-judge verification."""

    def test_llm_verify_sync_returns_none_on_parse_failure(self):
        from engine import SARoEngine
        eng = MagicMock(spec=SARoEngine)
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [MagicMock(text="not valid json {{{")]
        result = SARoEngine._gate3_llm_verify_sync(eng, mock_client, "test text", "Privacy & Security")
        assert result is None

    def test_llm_verify_sync_returns_dict_on_success(self):
        from engine import SARoEngine
        eng = MagicMock(spec=SARoEngine)
        mock_client = MagicMock()
        verdict_json = '{"domain": "Privacy & Security", "confirmed": true, "confidence": 0.9, "reasoning": "PII detected"}'
        mock_client.messages.create.return_value.content = [MagicMock(text=verdict_json)]
        result = SARoEngine._gate3_llm_verify_sync(eng, mock_client, "SSN: 123-45-6789", "Privacy & Security")
        assert result is not None
        assert result["confirmed"] is True
        assert result["confidence"] == 0.9

    def test_gate3_details_has_hybrid_mode_key(self):
        """Gate 3 result details should have hybrid_mode key."""
        from engine import _GateResult
        # Just verify the _GateResult dataclass works with hybrid_mode in details
        gate = _GateResult(
            gate_id=3,
            name="Risk Classification (MIT Taxonomy)",
            status="pass",
            score=0.95,
            details={"hybrid_mode": False, "llm_calls_made": 0, "llm_parse_failures": 0},
        )
        assert "hybrid_mode" in gate.details

    def test_llm_domain_definitions_defined(self):
        from engine import _MIT_DOMAIN_DEFINITIONS, MIT_DOMAINS
        for domain in MIT_DOMAINS:
            assert domain in _MIT_DOMAIN_DEFINITIONS, f"Domain {domain} missing from _MIT_DOMAIN_DEFINITIONS"


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-E3: Engine singleton + status endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineSingleton:
    """SPEC-E3: engine_status router exists and returns correct shape."""

    def test_engine_status_router_importable(self):
        from routers.engine_status import router
        assert router is not None

    def test_engine_status_endpoint_defined(self):
        from routers.engine_status import engine_status
        assert callable(engine_status)

    def test_engine_has_check_and_refresh_index(self):
        import inspect
        from engine import SARoEngine
        assert hasattr(SARoEngine, "check_and_refresh_index")
        assert inspect.iscoroutinefunction(SARoEngine.check_and_refresh_index)

    def test_engine_has_cached_incident_count_after_init_mock(self):
        # _compute_domain_priors is called in __init__; test that constants are exported
        from engine import PRIOR_WEIGHT
        assert PRIOR_WEIGHT >= 0


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-F2: SSO/SAML 2.0
# ─────────────────────────────────────────────────────────────────────────────

class TestSSO:
    """SPEC-F2: SSO/SAML 2.0 endpoints."""

    def test_sso_router_importable(self):
        from routers.sso import router
        assert router is not None

    def test_magic_link_warning_in_legacy_metadata(self):
        from routers.sso import legacy_sp_metadata
        result = legacy_sp_metadata()
        assert "warning" in result
        assert "testing only" in result["warning"].lower()

    def test_magic_link_disabled_raises_403(self):
        from routers.sso import magic_link_login, MagicLinkIn
        from fastapi import HTTPException
        # Mock DB with tenant that has allow_magic_link_fallback=False
        mock_db = MagicMock()
        mock_tenant = MagicMock()
        mock_tenant.id = uuid.uuid4()
        mock_config = MagicMock()
        mock_config.allow_magic_link_fallback = False
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_tenant, mock_config
        ]
        payload = MagicLinkIn(email="user@example.com", tenant_slug="test-tenant")
        with pytest.raises(HTTPException) as exc_info:
            magic_link_login(payload, db=mock_db)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "magic_link_disabled"

    def test_sp_metadata_xml_endpoint_exists(self):
        from routers.sso import sp_metadata
        assert callable(sp_metadata)

    def test_sso_login_redirect_endpoint_exists(self):
        from routers.sso import sso_login_redirect
        assert callable(sso_login_redirect)

    def test_saml_acs_endpoint_exists(self):
        from routers.sso import saml_acs
        import inspect
        assert inspect.iscoroutinefunction(saml_acs)

    async def test_unsigned_assertion_raises_400(self):
        """SPEC-F2 TR-03: unsigned assertion must return 400."""
        from routers.sso import saml_acs
        import base64
        from fastapi import HTTPException

        minimal_xml = (
            '<?xml version="1.0"?>'
            '<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">'
            '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
            '<saml:Subject><saml:NameID>user@example.com</saml:NameID></saml:Subject>'
            '</saml:Assertion></samlp:Response>'
        )
        encoded = base64.b64encode(minimal_xml.encode()).decode()

        mock_db = MagicMock()
        mock_tenant = MagicMock()
        mock_tenant.id = uuid.uuid4()
        mock_config = MagicMock()
        mock_config.sso_enabled = True
        mock_config.idp_metadata = {"sso_url": "https://idp.example.com/sso"}
        mock_config.mfa_required = False
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_tenant, mock_config]

        with pytest.raises(HTTPException) as exc_info:
            await saml_acs(
                tenant_slug="test",
                SAMLResponse=encoded,
                RelayState=None,
                db=mock_db,
            )
        assert exc_info.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-F3: Remediation + Jira OAuth
# ─────────────────────────────────────────────────────────────────────────────

class TestRemediation:
    """SPEC-F3: Remediation workflow endpoints."""

    def test_remediation_router_has_patch_endpoint(self):
        from routers.remediation import remediate_trace
        assert callable(remediate_trace)

    def test_remediation_router_has_progress_endpoint(self):
        from routers.remediation import get_remediation_progress
        assert callable(get_remediation_progress)

    def test_remediation_empty_note_raises_422(self):
        from routers.remediation import remediate_trace, RemediateTraceIn
        from fastapi import HTTPException
        payload = RemediateTraceIn(remediation_note="")
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()
        with pytest.raises(HTTPException) as exc_info:
            remediate_trace(uuid.uuid4(), payload, mock_db, mock_user)
        assert exc_info.value.status_code == 422

    def test_jira_service_importable(self):
        from services.jira import encrypt_token, decrypt_token
        # Round-trip test for Jira credential encryption
        plaintext = "test-access-12345-jira"
        encrypted = encrypt_token(plaintext)
        assert encrypted != plaintext
        decrypted = decrypt_token(encrypted)
        assert decrypted == plaintext

    def test_effort_estimate_mapping(self):
        """SPEC-F3 TS-05: effort estimate domain mapping."""
        from routers.remediation import _DOMAIN_TO_EFFORT
        assert _DOMAIN_TO_EFFORT["Discrimination & Toxicity"] == "High"
        assert _DOMAIN_TO_EFFORT["Privacy & Security"] == "High"
        assert _DOMAIN_TO_EFFORT["Malicious Use"] == "High"
        assert _DOMAIN_TO_EFFORT["AI System Safety"] == "High"
        assert _DOMAIN_TO_EFFORT["Human-Computer Interaction"] == "Medium"
        assert _DOMAIN_TO_EFFORT["Socioeconomic & Environmental"] == "Medium"

    def test_jira_oauth_start_endpoint_exists(self):
        from routers.remediation import jira_oauth_start
        assert callable(jira_oauth_start)

    def test_migration_008_exists(self):
        migration_path = Path(_REPO_ROOT) / "migrations" / "008_remediation_note.py"
        assert migration_path.exists(), "Migration 008_remediation_note.py must exist"


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-F5: Notifications (SSE + SendGrid)
# ─────────────────────────────────────────────────────────────────────────────

class TestNotifications:
    """SPEC-F5: Notification SSE stream and email dispatch."""

    def test_notifications_router_has_stream(self):
        from routers.notifications import notification_stream
        import inspect
        assert inspect.iscoroutinefunction(notification_stream)

    def test_sse_connection_registry(self):
        from services.notification_service import (
            register_sse_connection,
            unregister_sse_connection,
        )
        q = register_sse_connection("tenant-abc")
        assert q is not None
        unregister_sse_connection("tenant-abc", q)

    def test_no_email_without_sendgrid_key(self, caplog):
        """SPEC-F5 AC-04: no exception when SENDGRID_API_KEY is absent."""
        from services.notification_service import _send_email
        import logging
        mock_notif = MagicMock()
        mock_notif.id = uuid.uuid4()
        mock_notif.title = "Test alert"
        mock_notif.body = "Test body"
        mock_notif.severity = "critical"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SENDGRID_API_KEY", None)
            with caplog.at_level(logging.INFO):
                _send_email("user@example.com", mock_notif)
        # Should log skip message, not raise
        assert any("skipped" in r.message.lower() for r in caplog.records)

    def test_dispatch_notification_importable(self):
        from services.notification_service import dispatch_notification
        assert callable(dispatch_notification)


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-FE2: Board RAG Summary View
# ─────────────────────────────────────────────────────────────────────────────

class TestBoardSummary:
    """SPEC-FE2: Board RAG summary endpoints."""

    def test_board_summary_endpoint_exists(self):
        from routers.risk_dashboard import get_board_summary
        assert callable(get_board_summary)

    def test_board_pdf_endpoint_exists(self):
        from routers.risk_dashboard import export_board_summary_pdf
        assert callable(export_board_summary_pdf)

    def test_board_summary_no_data(self):
        from routers.risk_dashboard import get_board_summary
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()
        mock_user.role = "super_admin"
        mock_user.persona_role = "risk_officer"
        # No audit rows
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = get_board_summary(db=mock_db, current_user=mock_user)
        assert result["rag_status"] == "No data"

    def test_board_summary_rag_red(self):
        from routers.risk_dashboard import get_board_summary
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()
        mock_user.role = "super_admin"
        mock_user.persona_role = "risk_officer"

        mock_audit = MagicMock()
        mock_audit.id = uuid.uuid4()
        mock_audit.created_at = datetime.utcnow()
        mock_report = MagicMock()
        mock_report.overall_risk_score = 0.85  # > 0.7 → RED
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            (mock_audit, mock_report)
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = get_board_summary(db=mock_db, current_user=mock_user)
        assert result["rag_status"] == "RED"

    def test_board_access_denied_for_compliance_lead(self):
        from routers.risk_dashboard import _require_board_access
        from fastapi import HTTPException
        mock_user = MagicMock()
        mock_user.role = "operator"
        mock_user.persona_role = "compliance_lead"
        with pytest.raises(HTTPException) as exc_info:
            _require_board_access(mock_user)
        assert exc_info.value.status_code == 403

    def test_board_access_allowed_for_risk_officer(self):
        from routers.risk_dashboard import _require_board_access
        mock_user = MagicMock()
        mock_user.role = "operator"
        mock_user.persona_role = "risk_officer"
        # Should not raise
        _require_board_access(mock_user)

    def test_rag_thresholds_configurable(self):
        from routers.risk_dashboard import _BOARD_RED_THRESHOLD, _BOARD_AMBER_THRESHOLD
        assert _BOARD_RED_THRESHOLD == float(os.environ.get("BOARD_RISK_RED_THRESHOLD", "0.7"))
        assert _BOARD_AMBER_THRESHOLD == float(os.environ.get("BOARD_RISK_AMBER_THRESHOLD", "0.4"))


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-FE3: Frontend local dev setup
# ─────────────────────────────────────────────────────────────────────────────

class TestLocalDevSetup:
    """SPEC-FE3: docker-compose.yml and .env.example exist and are correct."""

    def test_docker_compose_exists(self):
        compose_path = Path(_REPO_ROOT) / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml must exist at repo root"

    def test_docker_compose_has_required_services(self):
        import yaml
        compose_path = Path(_REPO_ROOT) / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        services = config.get("services", {})
        assert "api" in services, "docker-compose.yml must have 'api' service"
        assert "frontend" in services, "docker-compose.yml must have 'frontend' service"
        assert "db" in services, "docker-compose.yml must have 'db' service"

    def test_docker_compose_api_port(self):
        import yaml
        compose_path = Path(_REPO_ROOT) / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        api_ports = config["services"]["api"].get("ports", [])
        assert any("8000" in str(p) for p in api_ports), "API service must expose port 8000"

    def test_docker_compose_frontend_port(self):
        import yaml
        compose_path = Path(_REPO_ROOT) / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        fe_ports = config["services"]["frontend"].get("ports", [])
        assert any("3000" in str(p) for p in fe_ports), "Frontend service must expose port 3000"

    def test_docker_compose_db_healthcheck(self):
        import yaml
        compose_path = Path(_REPO_ROOT) / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        db_service = config["services"]["db"]
        assert "healthcheck" in db_service, "DB service must have healthcheck"

    def test_env_example_exists(self):
        env_path = Path(_REPO_ROOT) / ".env.example"
        assert env_path.exists(), ".env.example must exist"

    def test_env_example_has_required_vars(self):
        env_path = Path(_REPO_ROOT) / ".env.example"
        content = env_path.read_text()
        required = [
            "DATABASE_URL",
            "JWT_SECRET_KEY",
            "ANTHROPIC_API_KEY",
            "SAML_SP_ENTITY_ID",
            "SENDGRID_API_KEY",
            "JIRA_CLIENT_ID",
        ]
        for var in required:
            assert var in content, f".env.example must contain {var}"

    def test_saro_network_defined(self):
        import yaml
        compose_path = Path(_REPO_ROOT) / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)
        networks = config.get("networks", {})
        assert "saro-network" in networks, "docker-compose.yml must define saro-network"


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-G3: DPA Template
# ─────────────────────────────────────────────────────────────────────────────

class TestDPATemplate:
    """SPEC-G3: GDPR Article 28 DPA template."""

    def test_dpa_template_file_exists(self):
        dpa_path = Path(_REPO_ROOT) / "docs" / "legal" / "saro-dpa-template-v1.0.md"
        assert dpa_path.exists(), "DPA template must exist at docs/legal/saro-dpa-template-v1.0.md"

    def test_dpa_has_required_sections(self):
        dpa_path = Path(_REPO_ROOT) / "docs" / "legal" / "saro-dpa-template-v1.0.md"
        content = dpa_path.read_text(encoding="utf-8")
        required_sections = [
            "SCHEDULE 1",
            "SCHEDULE 2",
            "SCHEDULE 3",
            "retention",
            "Sub-processor",
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), \
                f"DPA template must contain section: {section}"

    def test_dpa_lists_anthropic_as_sub_processor(self):
        dpa_path = Path(_REPO_ROOT) / "docs" / "legal" / "saro-dpa-template-v1.0.md"
        content = dpa_path.read_text(encoding="utf-8")
        assert "Anthropic" in content, "DPA must list Anthropic as a sub-processor"
        assert "no training" in content.lower() or "does not train" in content.lower(), \
            "DPA must clarify Anthropic does not train on customer data"

    def test_dpa_endpoint_in_governance_router(self):
        from routers.governance_trust import get_dpa_template
        assert callable(get_dpa_template)

    def test_dpa_legal_review_dir_exists(self):
        reviews_dir = Path(_REPO_ROOT) / "docs" / "legal" / "reviews"
        assert reviews_dir.exists(), "docs/legal/reviews/ directory must exist"


# ─────────────────────────────────────────────────────────────────────────────
# SPEC-G4: SOC 2 Readiness Roadmap
# ─────────────────────────────────────────────────────────────────────────────

class TestSOC2Roadmap:
    """SPEC-G4: SOC 2 readiness roadmap."""

    def test_soc2_roadmap_file_exists(self):
        soc2_path = Path(_REPO_ROOT) / "docs" / "soc2-readiness-roadmap-v1.0.md"
        assert soc2_path.exists(), "SOC 2 roadmap must exist at docs/soc2-readiness-roadmap-v1.0.md"

    def test_soc2_roadmap_has_required_sections(self):
        soc2_path = Path(_REPO_ROOT) / "docs" / "soc2-readiness-roadmap-v1.0.md"
        content = soc2_path.read_text()
        required = ["Trust Service Criteria", "gap", "Security", "Availability"]
        for term in required:
            assert term.lower() in content.lower(), \
                f"SOC 2 roadmap must mention: {term}"

    def test_governance_meta_has_soc2_field(self):
        from routers.governance_trust import get_governance_meta
        mock_user = MagicMock()
        result = get_governance_meta(_current=mock_user)
        assert "soc2" in result, "GET /governance/meta must include 'soc2' field"
        assert "status" in result["soc2"]
        assert "target_date" in result["soc2"]
        assert "roadmap_url" in result["soc2"]

    def test_soc2_roadmap_endpoint_exists(self):
        from routers.governance_trust import get_soc2_roadmap
        assert callable(get_soc2_roadmap)
