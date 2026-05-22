"""
Pydantic v2 request / response schemas for the SARO API.

Naming convention:
  *In   — request body / input
  *Out  — response body / output
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Literal["super_admin", "operator"] = "operator"
    tenant_id: uuid.UUID


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    persona_role: str | None = None
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime
    # CF-06: Persona RBAC fields (populated by /auth/me from PersonaPermission join)
    persona_role: str | None = None
    allowed_tabs: list[str] = []
    allowed_actions: list[str] = []

    model_config = {"from_attributes": True}


class BootstrapIn(BaseModel):
    """
    First-run payload: creates the initial tenant + super_admin account.
    Only accepted when the users table is empty (chicken-and-egg bootstrap).
    """

    org_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)


class TenantCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., pattern=r"^[a-z0-9\-]+$")


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Scan / Audit input
# ─────────────────────────────────────────────────────────────────────────────


class SampleIn(BaseModel):
    """A single text sample in a batch."""

    sample_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(..., min_length=1)
    # Optional demographic group label (used for Gate 2 fairness analysis)
    group: str | None = None
    # Ground-truth label if known (e.g. "toxic", "safe", "hallucination")
    label: str | None = None
    # CF-03: Sector/domain context for executive-mode TRACE language rendering
    domain_context: str | None = None
    # Any extra metadata the caller wants to attach
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def text_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Sample text must not be blank")
        return v


class AuditConfigIn(BaseModel):
    """Optional per-scan configuration overrides."""

    min_samples: int = Field(default=50, ge=50)
    confidence_threshold: float = Field(default=0.95, ge=0.5, le=1.0)
    incident_top_k: int = Field(default=5, ge=1, le=20)
    # Which frameworks to include in compliance mapping
    frameworks: list[str] = Field(
        default=["EU AI Act", "NIST AI RMF", "AIGP", "ISO 42001"]
    )
    # SARO-003: optional per-scan risk signal overrides
    risk_config: "RiskConfigIn | None" = None


class BatchIn(BaseModel):
    """
    Full batch submitted to /api/v1/scan.

    Minimum 50 samples enforced for statistical validity of fairness and risk metrics.
    """

    batch_id: str | None = Field(default=None)
    dataset_name: str | None = Field(default=None, max_length=255)
    samples: list[SampleIn] = Field(..., min_length=1)
    config: AuditConfigIn = Field(default_factory=AuditConfigIn)

    @field_validator("samples")
    @classmethod
    def enforce_minimum_samples(cls, v: list[SampleIn]) -> list[SampleIn]:
        if len(v) < 50:
            raise ValueError(
                f"Batch contains only {len(v)} samples. "
                "A minimum of 50 samples is required for reliable fairness and risk metrics "
                "(internal SARO methodology — statistical validity requirement)."
            )
        return v


# ─────────────────────────────────────────────────────────────────────────────
# saro_data framework batch format (POST /api/v1/scan/data)
# ─────────────────────────────────────────────────────────────────────────────


class SARoDataSampleIn(BaseModel):
    """
    One sample in the saro_data framework format.

    Fields mirror saro_data.schema.SampleOut:
      output       → maps to SampleIn.text
      prediction   → numeric risk score (stored in metadata)
      gender       → demographic group → SampleIn.group
      age          → stored in metadata
      ethnicity    → SampleIn.group (fallback when gender absent)
      ground_truth → 0=safe / 1=risky → SampleIn.label
    """

    output: str = Field(..., min_length=1)
    prediction: float | None = None
    gender: str | None = None
    age: int | None = None
    ethnicity: str | None = None
    ground_truth: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("output")
    @classmethod
    def output_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("output must not be blank")
        return v

    def to_sample_in(self, idx: int, prefix: str = "df") -> SampleIn:
        """Translate to the standard SampleIn used by the audit engine."""
        group = self.gender or self.ethnicity
        label: str | None = None
        if self.ground_truth is not None:
            label = "risky" if self.ground_truth == 1 else "safe"
        elif self.prediction is not None:
            label = "risky" if self.prediction >= 0.5 else "safe"
        return SampleIn(
            sample_id=f"{prefix}_{idx}",
            text=self.output,
            group=group,
            label=label,
            metadata={
                "prediction": self.prediction,
                "age": self.age,
                "ground_truth": self.ground_truth,
                **self.extra,
            },
        )


class SARoDataBatchIn(BaseModel):
    """
    Batch in the saro_data framework schema.

    Accepted by POST /api/v1/scan/data.  The endpoint translates this into
    a standard BatchIn and routes it through the same audit engine.

    Fields:
      model_type    — logical model category (e.g. "toxicity_generator")
      intended_use  — use-case under audit (e.g. "content_moderation")
      model_outputs — list of SARoDataSampleIn (≥50 required)
    """

    model_type: str = Field(..., min_length=1, max_length=200)
    intended_use: str = Field(..., min_length=1, max_length=200)
    model_outputs: list[SARoDataSampleIn] = Field(..., min_length=1)
    batch_id: str | None = None

    @field_validator("model_outputs")
    @classmethod
    def enforce_minimum_samples(cls, v: list[SARoDataSampleIn]) -> list[SARoDataSampleIn]:
        if len(v) < 50:
            raise ValueError(
                f"❌ Minimum 50 samples required for reliable fairness and risk metrics "
                f"(internal SARO methodology — statistical validity requirement). Got: {len(v)}."
            )
        return v

    def to_batch_in(self) -> BatchIn:
        """
        Translate SARoDataBatchIn → BatchIn for the audit engine.
        model_type is used as dataset_name; model_outputs become samples.
        """
        prefix = self.model_type.replace(" ", "_").lower()
        return BatchIn(
            batch_id=self.batch_id,
            dataset_name=self.model_type,
            samples=[s.to_sample_in(i, prefix) for i, s in enumerate(self.model_outputs)],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scan / Audit output
# ─────────────────────────────────────────────────────────────────────────────


class GateResultOut(BaseModel):
    gate_id: int
    name: str
    status: Literal["pass", "warn", "fail"]
    score: float = Field(..., ge=0.0, le=1.0)
    details: dict[str, Any]


class BayesianDomainScore(BaseModel):
    domain: str
    risk_probability: float = Field(..., ge=0.0, le=1.0)
    ci_lower: float
    ci_upper: float
    sample_count: int
    flagged_count: int


class BayesianScoresOut(BaseModel):
    overall: float
    by_domain: list[BayesianDomainScore]


class MITCoverageOut(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    covered_domains: list[str]
    uncovered_domains: list[str]
    total_risks_flagged: int
    domain_risk_counts: dict[str, int]


class SimilarIncidentOut(BaseModel):
    incident_id: str
    title: str
    category: str
    harm_type: str | None
    affected_sector: str | None
    date: str | None
    url: str | None
    similarity_score: float
    is_fixed: bool
    # SARO-007: low-confidence flag when similarity score is below threshold
    low_confidence: bool = False
    minimum_similarity_threshold: float = 0.15


class FixedDeltaOut(BaseModel):
    """
    Compares fixed vs not-fixed rates among similar historical incidents.

    delta > 0 → more fixed than unfixed (favourable historical outcome)
    delta < 0 → more unfixed incidents (ongoing risk pattern)
    """

    fixed_count: int
    unfixed_count: int
    total_similar: int
    delta: float  # = fixed_count/total - unfixed_count/total
    confidence: float


class AppliedRuleOut(BaseModel):
    framework: str
    rule_id: str
    title: str
    triggered_by: str
    obligations: str | None = None


class RemediationOut(BaseModel):
    domain: str
    suggestion: str
    priority: Literal["critical", "high", "medium", "low"]
    related_controls: list[str]


class AuditReportOut(BaseModel):
    audit_id: uuid.UUID
    status: Literal["completed", "failed", "partial"]
    batch_id: str | None
    dataset_name: str | None
    sample_count: int
    gates: list[GateResultOut]
    bayesian_scores: BayesianScoresOut
    mit_coverage: MITCoverageOut
    similar_incidents: list[SimilarIncidentOut]
    fixed_delta: FixedDeltaOut
    applied_rules: list[AppliedRuleOut]
    remediations: list[RemediationOut]
    confidence_score: float
    created_at: datetime
    # SARO-003: indicates whether tenant risk config overrides were applied
    risk_config_applied: bool = False
    # SARO-006: engine provenance for audit-of-the-auditor
    engine_version: str | None = None
    rule_pack_hash: str | None = None
    rule_change_warning: bool = False
    # SARO-007: timestamp of last corpus update for change detection
    incident_corpus_version: str | None = None


class AuditListItemOut(BaseModel):
    id: uuid.UUID
    batch_id: str | None
    dataset_name: str | None
    sample_count: int
    status: str
    mit_coverage_score: float | None
    fixed_delta: float | None
    overall_risk_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Demo / Trial Signup
# ─────────────────────────────────────────────────────────────────────────────


class DemoRequestIn(BaseModel):
    """Public signup form — no authentication required."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    contact_number: str | None = Field(default=None, max_length=50)
    company_name: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=2000)


class DemoRequestOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    contact_number: str | None
    company_name: str | None
    message: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DemoRequestStatusUpdateIn(BaseModel):
    status: Literal["pending", "contacted", "rejected", "converted"]


# ─────────────────────────────────────────────────────────────────────────────
# Audit Trace / Remedy
# ─────────────────────────────────────────────────────────────────────────────


class AuditTraceOut(BaseModel):
    """One trace record capturing a single check result during an audit."""
    id: uuid.UUID
    audit_id: uuid.UUID
    gate_id: int
    gate_name: str
    check_type: str
    check_name: str
    result: str
    reason: str | None
    detail_json: dict[str, Any] | None
    remediation_hint: str | None
    # SARO-DC-001: representative trigger signal (Gate 3: matched signal name,
    # Gate 2: parity metric string, Gate 4: triggered rule_id; never raw PII)
    signal_text: str | None = None
    # SARO-DC-002: top 10 sample_ids by weight for Gate 3 domain findings
    top_sample_ids: list[str] | None = None
    is_remediated: bool
    remediated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RemediateTraceIn(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


# ─────────────────────────────────────────────────────────────────────────────
# Enterprise Client Onboarding
# ─────────────────────────────────────────────────────────────────────────────


class IDPConfigIn(BaseModel):
    """Identity Provider configuration for SAML 2.0 / OIDC SSO."""
    provider: Literal[
        "okta", "azure_ad", "google_workspace", "pingfederate", "custom_saml", "custom_oidc"
    ]
    entity_id: str | None = Field(default=None, max_length=500, description="SAML Entity ID / OIDC Client ID")
    sso_url: str | None = Field(default=None, max_length=500, description="SSO login URL / OIDC authorization endpoint")
    metadata_url: str | None = Field(default=None, max_length=500, description="Metadata URL for auto-configuration")
    certificate: str | None = Field(default=None, description="X.509 certificate (PEM) for SAML assertion signing")
    client_secret: str | None = Field(default=None, max_length=500, description="OIDC client secret")
    tenant_domain: str | None = Field(default=None, max_length=255, description="Azure AD tenant domain / Google domain")
    extra: dict[str, Any] = Field(default_factory=dict)


class UserEnrollmentIn(BaseModel):
    """One user to enroll during client onboarding."""
    email: EmailStr
    role: Literal["super_admin", "operator"] = "operator"
    display_name: str | None = Field(default=None, max_length=255)


class ClientOnboardingIn(BaseModel):
    """Full enterprise client onboarding payload (admin-only)."""
    # Section 1: Client Details
    company_name: str = Field(..., min_length=2, max_length=255, description="Legal company name — must be globally unique")
    industry: str | None = Field(
        default=None,
        description="Financial Services | Healthcare | Legal & Compliance | Technology | Government | Other",
    )
    size: Literal["1–50", "51–200", "201–1,000", "1,000+"] | None = None
    primary_contact_name: str | None = Field(default=None, max_length=255)
    primary_contact_email: EmailStr | None = None
    # Section 2: Identity Provider
    sso_enabled: bool = True
    idp_config: IDPConfigIn | None = None
    # Section 3: User Enrollment
    initial_users: list[UserEnrollmentIn] = Field(default_factory=list, max_length=500)
    jit_provisioning_enabled: bool = True
    # Section 4: Security & Compliance
    mfa_required: bool = True
    allow_magic_link_fallback: bool = False
    scim_enabled: bool = False


class ClientConfigOut(BaseModel):
    """Response schema for a provisioned client."""
    tenant_id: uuid.UUID
    company_name: str
    slug: str
    industry: str | None
    size: str | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    sso_enabled: bool
    idp_provider: str | None
    scim_enabled: bool
    scim_endpoint: str | None
    # Only populated at creation time — shown once, then gone
    scim_bearer_token: str | None = None
    mfa_required: bool
    allow_magic_link_fallback: bool
    users_enrolled: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SCIMTokenRotateOut(BaseModel):
    """Returned once when a SCIM token is (re)generated — store it now."""
    scim_endpoint: str
    bearer_token: str
    warning: str = "Store this token securely. It will NOT be shown again."


class AuditEventOut(BaseModel):
    """Immutable audit event log entry."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    event_type: str
    event_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Enhanced Trace / Explainability
# ─────────────────────────────────────────────────────────────────────────────


class ChainOfThoughtStep(BaseModel):
    """One gate step in the chain-of-thought timeline."""
    step: int
    gate: str
    result: Literal["pass", "warn", "fail"]
    checks: list[dict[str, Any]]
    passed_count: int
    failed_count: int
    timestamp: str | None


class ExecutiveStep(BaseModel):
    """One plain-English TRACE step for compliance_lead executive mode (CF-01)."""
    label: str
    finding: str
    severity: Literal["Critical", "High", "Medium", "Low", "Pass"]


class EnhancedTraceOut(BaseModel):
    """Full, untruncated chain-of-thought trace for an audit. Zero truncation guaranteed."""
    id: uuid.UUID
    audit_id: uuid.UUID
    confidence: float | None
    model_version: str | None
    executive_summary: str | None
    chain_of_thought: dict[str, Any]  # {"steps": [...], "total_checks": N, "failed_checks": N}
    # CF-01: plain-English steps for Executive mode TRACE view
    executive_steps: list[ExecutiveStep] | None = None
    client_input_summary: dict[str, Any] | None
    client_output_summary: dict[str, Any] | None
    raw_prompt: str | None
    raw_response: str | None
    # Verbatim original prompt and AI output (single-output ingestion path)
    prompt_text: str | None = None
    raw_output_text: str | None = None
    # SHA-256 of the exported trace JSON for cryptographic verification
    export_hash: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Enterprise Dashboard
# ─────────────────────────────────────────────────────────────────────────────


class DashboardKPIOut(BaseModel):
    """KPI summary bar for the enterprise audit dashboard."""
    total_audits: int
    completed_audits: int
    failed_audits: int
    avg_risk_score: float | None
    avg_mit_coverage: float | None
    pending_remediations: int
    # risk_trend: list of (date_str, avg_risk_score) for the last 30 days
    risk_trend: list[dict[str, Any]]


# ─────────────────────────────────────────────────────────────────────────────
# Universal AI Output Ingestion
# ─────────────────────────────────────────────────────────────────────────────

_SOURCE_MODELS = Literal["grok", "claude", "openai", "sierra", "internal", "unknown"]


class SingleOutputAuditIn(BaseModel):
    """
    Single AI-generated output submitted for instant SARO risk/ethics/governance audit.

    SARO never calls external models — you provide the raw output directly.
    Feed any output from Grok, Claude, OpenAI, Sierra, or internal models.
    """
    prompt: str = Field(
        ..., min_length=1,
        description="The original prompt sent to the AI model (full text — never truncated).",
    )
    raw_output: str = Field(
        ..., min_length=1,
        description="The raw AI-generated output or agent response to audit.",
    )
    source_model: _SOURCE_MODELS = Field(
        default="unknown",
        description="The AI model that produced this output.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional key-value metadata (e.g. temperature, model_version, session_id).",
    )
    ingestion_method: Literal["api", "ui_form", "sdk_webhook"] = "api"


class SingleOutputAuditOut(BaseModel):
    """Immediate result of a single-output audit."""
    audit_id: uuid.UUID
    status: str
    source_model: str
    ingestion_method: str
    risk_score: float | None
    mit_coverage_pct: float | None
    confidence_score: float | None
    exceptions_count: int
    remediation_count: int
    trace_endpoint: str
    report: AuditReportOut
    created_at: datetime


class AuditMetadataOut(BaseModel):
    """Metadata attached to a universal output audit."""
    audit_id: uuid.UUID
    source_model: str | None
    ingestion_method: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Read-Only GitHub Integration
# ─────────────────────────────────────────────────────────────────────────────


class GitHubIntegrationConfigIn(BaseModel):
    """Configure SARO's read-only GitHub integration."""
    allowed_repos: list[str] = Field(
        ..., min_length=1, max_length=20,
        description="List of 'owner/repo' strings SARO may read (max 20).",
    )
    access_token: str = Field(
        ..., min_length=10,
        description=(
            "GitHub Personal Access Token with read-only scopes "
            "(repo:read / contents:read). Hashed before storage — never retrievable."
        ),
    )


class GitHubIntegrationOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    allowed_repos: list[str]
    is_active: bool
    last_scan_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GitHubScanResultOut(BaseModel):
    id: uuid.UUID
    audit_id: uuid.UUID
    repo_name: str
    file_path: str
    line_number: int | None
    snippet: str | None
    correlation_note: str | None
    finding_domain: str | None
    scan_hash: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditDashboardItemOut(BaseModel):
    """One row in the enterprise audit dashboard table."""
    id: uuid.UUID
    dataset_name: str | None
    audit_type: str
    created_at: datetime
    completed_at: datetime | None
    status: str
    overall_risk_score: float | None
    # "green" (≥85) | "yellow" (50–84) | "red" (<50) | None (not completed)
    risk_color: str | None
    mit_coverage_score: float | None
    exceptions_count: int
    remediated_count: int
    remediation_required: bool
    confidence_score: float | None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# CF-01: TRACE Export + Verification
# ─────────────────────────────────────────────────────────────────────────────


class TraceExportOut(BaseModel):
    """Signed JSON export of a TRACE record."""
    audit_id: uuid.UUID
    signed_json: dict[str, Any]
    export_hash: str
    signed_at: datetime


class TraceVerifyIn(BaseModel):
    export_hash: str


class TraceVerifyOut(BaseModel):
    valid: bool
    reason: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# CF-04: AIMS Document Lifecycle
# ─────────────────────────────────────────────────────────────────────────────


class AIMSDocumentIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    version: str = Field(..., min_length=1, max_length=50, description="Semver string e.g. '1.0.0'")
    effective_date: datetime | None = None
    owner_email: EmailStr


class AIMSDocumentOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    version: str
    effective_date: datetime | None
    owner_email: str
    linked_audit_ids: list[str]
    created_at: datetime
    updated_at: datetime | None
# SARO-001: Sample-level audit findings
# ─────────────────────────────────────────────────────────────────────────────


class SampleFindingOut(BaseModel):
    """One Gate 3 risk signal match persisted at the per-sample level."""
    id: uuid.UUID
    audit_id: uuid.UUID
    sample_id: str
    domain: str
    matched_signal: str
    matched_text_fragment: str | None
    weight: float
    created_at: datetime

    model_config = {"from_attributes": True}


class AIMSEvidencePackOut(BaseModel):
    """Structured JSON evidence pack for ISO 42001 auditor review."""
    document: AIMSDocumentOut
    linked_audits: list[dict[str, Any]]
    generated_at: datetime
    disclaimer: str = (
        "This evidence pack is generated by SARO v8.0.0. It does not constitute "
        "regulatory certification, legal advice, or compliance approval. Human review "
        "and sign-off by qualified personnel is required before any regulatory submission."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CF-05: Governance Trust Page
# ─────────────────────────────────────────────────────────────────────────────


class GovernanceDocMeta(BaseModel):
    version: str
    reviewed_at: datetime
    reviewer: str


class GovernanceMetaOut(BaseModel):
    nist: GovernanceDocMeta
    eu_ai_act: GovernanceDocMeta


# ─────────────────────────────────────────────────────────────────────────────
# CF-06: Persona RBAC
# ─────────────────────────────────────────────────────────────────────────────


class PersonaPermissionOut(BaseModel):
    persona_role: str
    allowed_tabs: list[str]
    allowed_actions: list[str]

    model_config = {"from_attributes": True}
class PaginatedSampleFindingOut(BaseModel):
    """SARO-DC-002: paginated SampleFinding results for a single AuditTrace record."""
    results: list[SampleFindingOut]
    page: int
    page_size: int
    total: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# SARO-003: Tenant risk configuration
# ─────────────────────────────────────────────────────────────────────────────


class RiskConfigIn(BaseModel):
    """Per-scan or per-tenant overrides for Gate 3 risk signal weights and keyword suppressions."""
    domain_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Override domain weights (0.0–1.0). E.g. {'Privacy & Security': 0.95}",
    )
    keyword_suppressions: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Keywords to suppress per domain. E.g. {'AI System Safety': ['fail']}",
    )

    @field_validator("domain_weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        for domain, w in v.items():
            if not (0.0 <= w <= 1.0):
                raise ValueError(f"Weight for '{domain}' must be between 0.0 and 1.0, got {w}")
        return v


class TenantRiskConfigOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    domain_weights: dict[str, float]
    keyword_suppressions: dict[str, list[str]]
    max_weight_ceiling: float
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# SARO-004: NIST AI RMF coverage report
# ─────────────────────────────────────────────────────────────────────────────


class NistSubcategoryOut(BaseModel):
    """One NIST AI RMF subcategory entry in the coverage report."""
    subcategory_id: str
    function_name: str
    description: str | None
    # "mapped" | "partial" | "not_covered" | "requires_human_assessment"
    status: str
    version: str = "AI RMF 1.0"


class NistCoverageReportOut(BaseModel):
    """Full NIST AI RMF coverage report across all 72 subcategory outcomes."""
    engine_version: str
    total_subcategories: int
    mapped_count: int
    partial_count: int
    not_covered_count: int
    requires_human_assessment_count: int
    subcategories: list[NistSubcategoryOut]
    generated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# SARO-005: ISO 42001 Annex A generated document
# ─────────────────────────────────────────────────────────────────────────────


class Iso42001DocumentOut(BaseModel):
    id: uuid.UUID
    audit_id: uuid.UUID
    generated_by_user_id: uuid.UUID | None
    format: str
    content: str
    content_hash: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# SARO-006: Engine integrity
# ─────────────────────────────────────────────────────────────────────────────


class EngineIntegrityOut(BaseModel):
    """Current engine version and rule pack integrity state."""
    engine_version: str
    rule_pack_hash: str
    compliance_matrix_version: str
    checked_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# SARO-007: Incident corpus statistics
# ─────────────────────────────────────────────────────────────────────────────


class IncidentCorpusStatsOut(BaseModel):
    """Quality and currency statistics for the AI incident similarity corpus."""
    total_incidents: int
    count_by_category: dict[str, int]
    count_by_harm_type: dict[str, int]
    date_range_earliest: str | None
    date_range_latest: str | None
    pct_fixed: float
    last_corpus_update: datetime | None
    minimum_similarity_threshold: float = 0.15
