"""
SQLAlchemy ORM models for the SARO platform.

Existing tables (populated by import_*.py scripts):
  mit_risks, eu_ai_act_rules, nist_ai_rmf_controls,
  aigp_principles, governance_rules, ai_incidents

New tables added here:
  tenants, users, audits, scan_reports, audit_traces, demo_requests
"""
from __future__ import annotations

import enum as py_enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Tenant & User (RBAC: Super Admin + Operator)
# ─────────────────────────────────────────────────────────────────────────────


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    users: Mapped[list[User]] = relationship(back_populates="tenant")
    audits: Mapped[list[Audit]] = relationship(back_populates="tenant")
    client_config: Mapped["ClientConfig | None"] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Roles: "super_admin" | "operator"
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="operator")
    # Persona: "compliance_lead" | "risk_officer" | "ai_auditor" | "admin" | None
    persona_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    audits: Mapped[list[Audit]] = relationship(back_populates="user")


# ─────────────────────────────────────────────────────────────────────────────
# Audits & Reports
# ─────────────────────────────────────────────────────────────────────────────


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    batch_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # status: "pending" | "running" | "completed" | "failed"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    # S-101: verbatim text for single-output ingestion path
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped[Tenant] = relationship(back_populates="audits")
    user: Mapped[User | None] = relationship(back_populates="audits")
    report: Mapped[ScanReport | None] = relationship(
        back_populates="audit", uselist=False
    )
    traces: Mapped[list["AuditTrace"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )


class ScanReport(Base):
    """Persisted full audit report (JSON blob + key scalar metrics)."""

    __tablename__ = "scan_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        unique=True,
    )
    # Top-level scalar metrics (indexed for dashboarding)
    mit_coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fixed_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Full structured report stored as JSON
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    # SARO-006: engine provenance fields for audit-of-the-auditor
    engine_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_pack_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compliance_matrix_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    audit: Mapped[Audit] = relationship(back_populates="report")


class AuditMetadata(Base):
    """
    1:1 extension of Audit for universal AI output ingestion metadata.

    Kept separate from Audit to preserve existing audit data when new fields
    are added (avoids schema-healing drop/recreate of the audits table).
    """
    __tablename__ = "audit_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # source_model: "grok" | "claude" | "openai" | "sierra" | "internal" | "unknown"
    source_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # ingestion_method: "api" | "ui_form" | "sdk_webhook" | "batch_scan"
    ingestion_method: Mapped[str] = mapped_column(String(50), nullable=False, default="batch_scan")
    # GAP-009: business vertical for dashboard filtering
    vertical: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Optional S3 object keys for large prompt/output storage
    prompt_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditTrace(Base):
    """
    Granular trace record for each check performed during an audit.

    One row per gate result, domain risk signal, or compliance rule trigger.
    Drives the Remedy screen: failed/warn traces are surfaced for operator review.
    """
    __tablename__ = "audit_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False
    )
    gate_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gate_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # check_type: "gate_result" | "risk_domain" | "compliance_rule"
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    check_name: Mapped[str] = mapped_column(String(500), nullable=False)
    # result: "pass" | "fail" | "warn" | "flagged" | "triggered"
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    remediation_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SARO-DC-001: representative trigger signal for this finding (never raw PII)
    signal_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # SARO-DC-002: top 10 sample_ids by weight for Gate 3 domain findings
    top_sample_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Remedy workflow fields
    is_remediated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remediated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remediated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # AUD-001: SHA-256 hash chain for tamper-evident audit logs.
    # event_hash: SHA-256 hex of this event's canonical payload (build_event_payload).
    # prev_hash: event_hash of the preceding event in this audit's chain (NULL = genesis).
    # Rows written before migration 009 carry event_hash=LEGACY_SENTINEL.
    # Column is nullable in DB (migration 003); _persist_traces() always supplies a value.
    # No ORM-level default — callers must set event_hash explicitly so omissions fail loudly.
    event_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, deferred=True)
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, deferred=True)

    audit: Mapped["Audit"] = relationship(back_populates="traces")


# ─────────────────────────────────────────────────────────────────────────────
# Reference tables (read-only, populated by import_*.py scripts)
# ─────────────────────────────────────────────────────────────────────────────


class MITRisk(Base):
    __tablename__ = "mit_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ev_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paper_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_ev: Mapped[str | None] = mapped_column(Text, nullable=True)
    causal_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    causal_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    causal_timing: Mapped[str | None] = mapped_column(String(100), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sub_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EUAIActRule(Base):
    __tablename__ = "eu_ai_act_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    obligations_providers: Mapped[str | None] = mapped_column(Text, nullable=True)
    obligations_users: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    annex_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class NISTControl(Base):
    __tablename__ = "nist_ai_rmf_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    function_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subcategory_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_actions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SARO-004: framework version for traceability
    version: Mapped[str | None] = mapped_column(String(50), nullable=True, default="AI RMF 1.0")
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AIGPPrinciple(Base):
    __tablename__ = "aigp_principles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subtopic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    key_principles: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GovernanceRule(Base):
    __tablename__ = "governance_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    framework_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    obligations: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AIIncident(Base):
    __tablename__ = "ai_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    harm_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    affected_sector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Whether the incident was remediated/resolved
    is_fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Enterprise Client Configuration (1:1 extension of Tenant)
# ─────────────────────────────────────────────────────────────────────────────


class ClientConfig(Base):
    """
    Enterprise client SSO/SCIM/IDP configuration — 1:1 extension of Tenant.

    Stores identity provider metadata, SCIM provisioning config, MFA settings,
    and contact information for the enterprise onboarding workflow.
    """
    __tablename__ = "client_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # size: "1–50" | "51–200" | "201–1,000" | "1,000+"
    size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # SSO / IDP
    sso_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # idp_provider: "okta" | "azure_ad" | "google_workspace" | "pingfederate" | "custom_saml" | "custom_oidc"
    idp_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idp_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # SCIM 2.0
    scim_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scim_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scim_bearer_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Security & Compliance
    mfa_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_magic_link_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warning_banner_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # LIVE-005: per-tenant JWT session length in minutes.
    # None → use global ACCESS_TOKEN_EXPIRE_MINUTES env var (default 480 = 8h).
    # Set to e.g. 480 for enterprise SSO sessions, 60 for high-security tenants.
    token_expire_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # LIVE-004: data region for GDPR / DPA compliance.
    # "EU" → EU data residency required; GitHub integration blocked until DPA amended.
    # "US" or None → no EU-specific restrictions.
    data_region: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="client_config")


# ─────────────────────────────────────────────────────────────────────────────
# Immutable Audit Event Log
# ─────────────────────────────────────────────────────────────────────────────


class AuditEvent(Base):
    """
    Immutable event log — every state change is appended here, never updated.
    Drives compliance trails for client onboarding, user enrollment, SSO config.
    """
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # event_type: "client_created" | "sso_configured" | "scim_token_rotated"
    # | "user_enrolled" | "mfa_policy_changed" | "sso_test_passed" | "sso_test_failed"
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# Enhanced Trace / Chain-of-Thought (one per completed audit)
# ─────────────────────────────────────────────────────────────────────────────


class EnhancedTrace(Base):
    """
    Full chain-of-thought trace for an audit — zero truncation.

    Synthesised on first access from AuditTrace records + ScanReport JSON,
    then persisted for subsequent reads.  Drives the TRACE / Explainability view.
    """
    __tablename__ = "enhanced_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # chain_of_thought: {"steps": [...], "total_checks": N, "failed_checks": N}
    chain_of_thought: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # executive_steps: [{label, finding, severity}] — plain-English for compliance lead
    executive_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Representative sample metadata (no raw PII stored)
    client_input_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    client_output_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Full raw prompt / response stored as text (expandable in UI)
    raw_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Verbatim original prompt and AI output (universal ingestion — never truncated)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SHA-256 of the exported trace JSON (for signed export verification)
    export_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# Read-Only GitHub Integration
# ─────────────────────────────────────────────────────────────────────────────


class GitHubIntegration(Base):
    """
    Read-only GitHub integration configuration per tenant.

    SARO only reads repositories the client explicitly grants.
    Scopes: repo:contents:read, repo:metadata (read-only).
    No code is stored — only scan results + file hashes.
    """
    __tablename__ = "github_integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # JSON array of "owner/repo" strings that SARO may read
    allowed_repos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # SHA-256 of the Personal Access Token — never stored in plaintext
    access_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GitHubScanResult(Base):
    """
    One correlated file location from a read-only GitHub scan.

    Each row ties an audit finding to a specific file in the client's repo,
    with a short snippet (no full file content stored) and a remediation note.
    Every scan is logged immutably in audit_events.
    """
    __tablename__ = "github_scan_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False
    )
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Short snippet only — never the full file (privacy + security)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SHA-256 of the file content at scan time (for integrity tracking)
    scan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DemoRequest(Base):
    """
    Prospective customer demo/trial signup request.
    Submitted from the public login page — no authentication required.
    """
    __tablename__ = "demo_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status: "pending" | "contacted" | "rejected" | "converted"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Persona RBAC (CF-06)
# Persona RBAC (one row per persona role — seeded by migration 004)
# ─────────────────────────────────────────────────────────────────────────────


class PersonaPermission(Base):
    """
    Defines which UI tabs and API actions each persona_role may access.

    Rows are seeded once at startup (idempotent).
    persona_role: "compliance_lead" | "risk_officer" | "ai_auditor"
    allowed_tabs: JSON array of tab identifiers (match frontend route keys)
    allowed_actions: JSON array of action strings (e.g. "create_aims_document")
    """
    __tablename__ = "persona_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_role: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    allowed_tabs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    allowed_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# AIMS Document Lifecycle (CF-04)
# ─────────────────────────────────────────────────────────────────────────────


class AIMSDocument(Base):
    """
    AI Management System document for ISO 42001 evidence linking.

    Stores document metadata and links to completed audits.
    linked_audit_ids: JSON array of audit UUIDs (as strings).
    """
    __tablename__ = "aims_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # semver string e.g. "1.0.0"
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # JSON array of audit UUID strings
    linked_audit_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
# SARO-001: Sample-level audit evidence (per-sample Gate 3 findings)
# ─────────────────────────────────────────────────────────────────────────────


class SampleFinding(Base):
    """
    Persists per-sample Gate 3 risk signal matches.

    Enables governance leads to drill from an AuditTrace domain flag down to
    the exact samples that triggered it.  PII-containing matched_text_fragment
    fields are redacted at write time — raw SSNs/cards are never stored here.
    """
    __tablename__ = "sample_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False
    )
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    # The keyword or pattern identifier that matched (e.g. "keyword:ssn")
    matched_signal: Mapped[str] = mapped_column(String(500), nullable=False)
    # Short redacted snippet from the sample text (max 200 chars, PII masked)
    matched_text_fragment: Mapped[str | None] = mapped_column(String(200), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    audit: Mapped["Audit"] = relationship()


# ─────────────────────────────────────────────────────────────────────────────
# SARO-003: Per-tenant risk signal configuration overrides
# ─────────────────────────────────────────────────────────────────────────────


class TenantRiskConfig(Base):
    """
    Tenant-level overrides for Gate 3 risk domain weights and keyword suppressions.

    super_admin sets the tenant ceiling; operator can override per-scan within
    those bounds.  Applied at audit-start; never mutates the global _RISK_SIGNALS.
    """
    __tablename__ = "tenant_risk_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # domain → weight float (0.0–1.0); JSON: {"Privacy & Security": 0.95, ...}
    domain_weights: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # domain → list of keywords to suppress; JSON: {"AI System Safety": ["fail"]}
    keyword_suppressions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Maximum weight ceiling an operator may set; enforced at scan time
    max_weight_ceiling: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# SARO-005: ISO 42001 Annex A generated documents (immutable versioned records)
# ─────────────────────────────────────────────────────────────────────────────


class Iso42001Document(Base):
    """
    Immutable versioned record of a generated ISO 42001 Annex A document.

    Each generation creates a new row; old rows are never edited through the API.
    content_hash ensures the document content has not been altered post-generation.
    """
    __tablename__ = "iso42001_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False
    )
    generated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # "markdown" | "pdf" (PDF generated on-demand from markdown)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="markdown")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA-256 of content at generation time for immutability verification
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Version counter within this audit (1, 2, 3 …)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    audit: Mapped["Audit"] = relationship()
# Notifications (migration 006)
# ─────────────────────────────────────────────────────────────────────────────


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # values: threshold_breach | drift_alert | framework_update | system
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # values: critical | high | medium | low
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


# ─────────────────────────────────────────────────────────────────────────────
# S-001: HuggingFace Sample Queue
# ─────────────────────────────────────────────────────────────────────────────


class HFSampleStatus(py_enum.Enum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"


# ─────────────────────────────────────────────────────────────────────────────
# EVF — External SME Validation Framework (SARO-RISK-001)
# Sprint 1: FR-EVF-05 (SME Engagement Tracking) + FR-EVF-08 (Validation Gate)
# ─────────────────────────────────────────────────────────────────────────────


class EVFFramework(py_enum.Enum):
    EU_AI_ACT = "EU_AI_ACT"
    NIST_AI_RMF = "NIST_AI_RMF"
    AIGP = "AIGP"
    ISO_42001 = "ISO_42001"


class SMEEngagementState(py_enum.Enum):
    SHORTLISTED = "SHORTLISTED"
    COI_CLEARED = "COI_CLEARED"
    SOW_ISSUED = "SOW_ISSUED"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    DRAFT_QCO_RECEIVED = "DRAFT_QCO_RECEIVED"
    QCO_APPROVED = "QCO_APPROVED"
    PUBLISHED = "PUBLISHED"
    RENEWAL_TRIGGERED = "RENEWAL_TRIGGERED"


class SMEEngagement(Base):
    """
    One SME firm engagement per framework per validation cycle.

    State machine: SHORTLISTED → COI_CLEARED → SOW_ISSUED →
    REVIEW_IN_PROGRESS → DRAFT_QCO_RECEIVED → QCO_APPROVED →
    PUBLISHED → RENEWAL_TRIGGERED
    """
    __tablename__ = "evf_sme_engagements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sme_firm_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sme_key_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sme_credential: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # EVFFramework enum value stored as string
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    # SMEEngagementState enum value stored as string
    state: Mapped[str] = mapped_column(String(50), nullable=False, default=SMEEngagementState.SHORTLISTED.value)
    state_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transitions: Mapped[list["SMEEngagementTransition"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan", order_by="SMEEngagementTransition.created_at"
    )
    gate: Mapped["ValidationGate | None"] = relationship(
        back_populates="engagement", uselist=False, cascade="all, delete-orphan"
    )


class SMEEngagementTransition(Base):
    """
    Append-only hash-chained log of every state transition for an engagement.
    Tamper-evident: each row's event_hash covers prev_hash + transition payload.
    """
    __tablename__ = "evf_engagement_transitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evf_sme_engagements.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(50), nullable=False)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    engagement: Mapped["SMEEngagement"] = relationship(back_populates="transitions")


class ValidationGate(Base):
    """
    7-item checklist that must be fully completed before any QCO can be
    published for this engagement (FR-EVF-08). Locked once all items are true.
    """
    __tablename__ = "evf_validation_gates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evf_sme_engagements.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # Gate items — each becomes True when evidence is recorded
    coi_declared_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    coi_evidence_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sow_executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sow_evidence_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_package_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_package_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    product_demo_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    product_demo_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    draft_qco_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draft_qco_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    saro_legal_review_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legal_signoff_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    qco_approved_ref_assigned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    qco_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Locked when all 7 items are True — no further edits permitted
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    engagement: Mapped["SMEEngagement"] = relationship(back_populates="gate")


# ─────────────────────────────────────────────────────────────────────────────
# EVF Sprint 2: FR-EVF-10 (QCO Registry) + FR-EVF-20/21 (Publication Audit)
# ─────────────────────────────────────────────────────────────────────────────


class QCORegistry(Base):
    """
    Immutable QCO registry. Records become immutable once published=True.
    Immutability is enforced at the application layer (evf_qco_service.py).

    Hash chain: each published record carries prev_hash + record_hash covering
    all immutable fields so tampering with any published entry breaks the chain.
    FR-EVF-10 | SARO-RISK-001
    """
    __tablename__ = "evf_qco_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Format: SARO-QCO-{FRAMEWORK}-{YYYY}-{SEQ:03d}
    qco_reference_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # EVFFramework enum value stored as string
    framework_covered: Mapped[str] = mapped_column(String(50), nullable=False)
    saro_version_assessed: Mapped[str] = mapped_column(String(50), nullable=False)
    sme_firm: Mapped[str] = mapped_column(String(255), nullable=False)
    sme_credential: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Set at publish time (FR-EVF-13: expiry_date <= issue_date + 365 days)
    issue_date: Mapped[date | None] = mapped_column(DateTime(timezone=False), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(DateTime(timezone=False), nullable=True)
    scope_boundary_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Access-controlled signed URL; SHA-256 of the document for integrity
    document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evf_sme_engagements.id", ondelete="SET NULL"), nullable=True
    )
    # Publication state — once True, record is immutable
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Hash chain (populated at publish time)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Renewal links
    renews_qco_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evf_qco_registry.id", ondelete="SET NULL"), nullable=True
    )
    superseded_by_qco_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evf_qco_registry.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QCOPublicationEvent(Base):
    """
    Append-only hash-chained log of every external compliance claim publication.
    Immutability enforced by DB trigger (migration 012).

    Five required fields per AC-21a:
      timestamp, artefact_identifier, qco_reference_number,
      publisher_user_id, distribution_channel

    FR-EVF-20, FR-EVF-21 | SARO-RISK-001
    """
    __tablename__ = "evf_publication_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Required field 1: server-set UTC timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Required field 2: identifies the artefact that triggered the publication
    artefact_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    # Required field 3: soft FK to QCORegistry (string ref for resilience)
    qco_reference_number: Mapped[str] = mapped_column(String(100), nullable=False)
    # Required field 4: identity of the user who triggered publication
    publisher_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Required field 5: channel through which the claim was published
    # Allowed: API | REPORT_PDF | DASHBOARD | SALES_DECK | WEBSITE | PARTNER_PORTAL
    distribution_channel: Mapped[str] = mapped_column(String(50), nullable=False)
    # Hash chain
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Idempotency key — deduplication for retries
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# EVF Sprint 3: FR-EVF-13 (QCO Expiry Notifications)
# ─────────────────────────────────────────────────────────────────────────────


class QCOExpiryNotification(Base):
    """
    Idempotent log of every QCO expiry notification dispatched.
    One row per (qco_id, notification_type, expiry_date) — never duplicated.

    Notification types:
      T_MINUS_60  — renewal trigger at 60-day warning
      T_MINUS_30  — 30-day reminder
      T_MINUS_7   — 7-day reminder
      EXPIRED     — QCO expired, validation reverted to Tier 2
      SALES_NOTIFY — 24h Sales alert (AC-13c)

    FR-EVF-13 | SARO-RISK-001
    """
    __tablename__ = "evf_expiry_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qco_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evf_qco_registry.id", ondelete="SET NULL"), nullable=True
    )
    qco_reference_number: Mapped[str] = mapped_column(String(100), nullable=False)
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    # T_MINUS_60 | T_MINUS_30 | T_MINUS_7 | EXPIRED | SALES_NOTIFY
    notification_type: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_in_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Idempotency key: "{qco_id}:{notification_type}:{reference_date}"
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
class HFSampleQueue(Base):
    """
    Queue of individual samples pulled from HuggingFace datasets.

    The hf_sampler script inserts rows here; the hf_processor router picks up
    'pending' rows and runs them through the SARO engine, updating status to
    'processed' or 'failed'.
    """
    __tablename__ = "hf_sample_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    vertical: Mapped[str] = mapped_column(String(50), nullable=False)
    source_dataset: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_model: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    # status: "pending" | "processing" | "processed" | "failed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ─────────────────────────────────────────────────────────────────────────────
# SARO Data Framework — Evaluation Run tracking
# ─────────────────────────────────────────────────────────────────────────────


class EvaluationRun(Base):
    """
    Tracks every execution of the saro-data-framework TestRunner.

    Status values: running | completed | partial | failed
    Triggered by:  api | schedule | ci | manual
    """
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    datasets_requested: Mapped[str] = mapped_column(Text, nullable=False, default="all")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    datasets_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    datasets_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    datasets_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    datasets_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_samples_uploaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    elapsed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# SAR-013: EU AI Act AI System Inventory
# ─────────────────────────────────────────────────────────────────────────────


class AISystem(Base):
    """
    Persistent inventory record for an AI system in scope for EU AI Act Art. 49.

    CRITICAL: eu_ai_act_risk_tier is a HUMAN governance decision per EU AI Act Art. 14.
    The audit engine MUST NEVER set this field automatically — it may only suggest.
    Only compliance_lead and risk_officer personas may write eu_ai_act_risk_tier via API.
    """
    __tablename__ = "ai_systems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_owner: Mapped[str | None] = mapped_column(String(320), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_context: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # EU AI Act risk tier — HUMAN DECISION ONLY (Art. 14). Never set by engine.
    # Values: "unacceptable" | "high" | "limited" | "minimal" | None (not classified)
    eu_ai_act_risk_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_audit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SystemAudit(Base):
    """Junction table linking AI systems to their audit records."""
    __tablename__ = "system_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_systems.id", ondelete="CASCADE"), nullable=False
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# SAR-010: Unified Control Library
# ─────────────────────────────────────────────────────────────────────────────


class Control(Base):
    """
    Single unified control entry in the SARO control library.

    Each control appears once and is tagged to the frameworks it satisfies
    via ControlFrameworkMapping (many-to-many). Rule packs are the technical
    implementation of a control — controls are the governance-layer abstraction.
    """
    __tablename__ = "controls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Human-readable control identifier, e.g. "CTRL-RISK-001"
    control_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "preventive" | "detective" | "corrective" | "compensating"
    control_type: Mapped[str] = mapped_column(String(50), nullable=False, default="detective")
    # "active" | "planned" | "deprecated"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Aggregate count of audit traces that serve as evidence for this control (denormalised)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_assessed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ControlFrameworkMapping(Base):
    """
    Many-to-many junction: one control maps to one framework+clause reference.

    A single control may have multiple rows here (one per framework clause it
    satisfies), enabling cross-framework coverage queries.
    """
    __tablename__ = "control_framework_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False
    )
    # "EU_AI_ACT" | "NIST_AI_RMF" | "AIGP" | "ISO_42001"
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "Art.9", "Cl.6.1", "GOVERN-1.7", "Pr.4"
    clause_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
