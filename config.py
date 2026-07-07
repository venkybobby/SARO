"""
Centralized application settings (SARO-H08).

Wraps environment-variable access for security-sensitive configuration in a
single Pydantic ``BaseSettings`` model. This gives one place to see which
secrets the app depends on, with type coercion and consistent defaults.

Design notes:
  - All fields are Optional with safe defaults so ``Settings()`` never raises
    at import time — secrets may not be injected yet during early startup
    (Railway/Koyeb cold start). Call sites that require a secret must check
    for ``None``/empty and raise their own descriptive RuntimeError, exactly
    as the previous ``os.environ.get(...)`` call sites did.
  - ``settings`` is a module-level singleton. Tests that need to override a
    value should monkeypatch the relevant attribute on ``settings`` directly,
    e.g. ``monkeypatch.setattr(config.settings, "jwt_secret_key", "test")``.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # ── Auth / JWT ───────────────────────────────────────────────────────────
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # ── Database / Supabase ──────────────────────────────────────────────────
    database_url: str | None = None
    db_sslmode: str = "require"
    supabase_project_ref: str | None = None

    # ── SAML SSO (SPEC-F2) ───────────────────────────────────────────────────
    saml_sp_entity_id: str = "https://saro.app/sp"
    saml_sp_acs_url: str = "https://saro.app/api/v1/sso/acs"
    saml_sp_cert: str | None = None
    saml_sp_key: str | None = None

    # ── Notifications ────────────────────────────────────────────────────────
    sendgrid_api_key: str | None = None

    # ── Rule-pack versioning (STORY-RPV-001) ─────────────────────────────────
    # When TRUE, LEGACY_UNREVIEWED (and status-less, e.g. NIST) rule rows are
    # includable in a published snapshot, carrying a version-level caveat. When
    # FALSE, only SME_VALIDATED rows are includable. DRAFT_UNVALIDATED / RETIRED
    # are never includable regardless of this flag.
    saro_snapshot_include_legacy: bool = True

    # ── Rule-pack evaluation pin (STORY-RPV-002) ─────────────────────────────
    # PERMISSIVE: pin the latest PUBLISHED snapshot (never the working copy); if
    #   none published, pin is None (PRE-VERSIONING) and evaluation proceeds.
    # STRICT: refuse to evaluate when no version is published or the working copy
    #   has drifted from the latest published version beyond tolerance.
    # A broken snapshot chain refuses in BOTH modes (integrity incident).
    saro_rule_pack_eval_mode: str = "PERMISSIVE"

    # ── Rule-pack visibility on customer surfaces (STORY-CHUB-011) ────────────
    # When True, LEGACY_UNREVIEWED rule rows are visible in default customer views
    # (provisionally-visible legacy), carrying a "pending validation" indicator that
    # is shown to internal personas only. When False, legacy rows are hidden from
    # default views too. DRAFT_UNVALIDATED / RETIRED / NULL are never in default
    # views regardless of this flag.
    saro_show_legacy_rules: bool = True

    # ── SARO self-audit spine (STORY-META-001) ───────────────────────────────
    # Hot-retention floor for audit_events before archival (never silent deletion).
    saro_audit_retention_days: int = 365

    # ── Finding disposition lifecycle (STORY-DISP-001) ───────────────────────
    # When True, a WAIVED disposition's approver must differ from the acknowledger
    # AND the waive actor (four-eyes). Per-tenant policy in v1 defaults to this flag.
    saro_disposition_four_eyes: bool = False
    # Max waiver horizon (days): a waiver may not indefinitely suppress a finding.
    # expiry must be in (today, today + this]. Reject past/absurd-future expiries.
    saro_disposition_max_waiver_days: int = 180

    # ── PHI-free usage metering (STORY-MTR-001) ──────────────────────────────
    # Per-meter soft thresholds: crossing RECORDS + NOTIFIES; it never enforces a
    # cutoff (v1 never silently drops evaluations). {} means no thresholds configured.
    saro_metering_thresholds: dict = {}
    # Reconciliation drift tolerance: meter total vs authoritative count beyond this
    # fraction raises a data-quality finding.
    saro_metering_drift_tolerance: float = 0.005

    # ── Observation coverage / gaps (STORY-COV-001) ──────────────────────────
    # A (system, adapter) whose latest checkpoint is older than this many seconds is
    # considered blind — a gap opens. Per-adapter cadence + tolerance in one knob (v1).
    saro_coverage_cadence_seconds: int = 300

    # ── Live observation-checkpoint emission (STORY-COV-002) ──────────────────
    # Coalescing window for live emission: at most one checkpoint per
    # (tenant, system, adapter) per bucket. Must be < cadence so an actively-observed
    # window always leaves at least one heartbeat before a gap could open.
    saro_coverage_bucket_seconds: int = 60
    # When a fresh checkpoint (new bucket) is created on the live audit path, also run an
    # opportunistic gap sweep so gaps auto-open with no external scheduler. Fail-open; set
    # False to disable the sweep (e.g. under a dedicated scheduler) without a code change.
    saro_coverage_auto_sweep: bool = True


settings = Settings()
