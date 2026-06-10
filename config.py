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


settings = Settings()
