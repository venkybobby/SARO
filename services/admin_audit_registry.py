"""STORY-366 — admin-mutation audit coverage registry.

The problem this solves: "all admin mutation endpoints write to the audit log"
is unenforceable as prose. Here every mutating route (POST/PUT/PATCH/DELETE) is
classified exactly once, and `tests/test_story366_admin_audit_coverage.py` fails
when a route is unclassified — so a NEW admin endpoint cannot silently ship
without an audit decision being made about it.

Two classes:

* ``AUDITED`` — admin/config actions (tenancy, roles, config, adapter/integration
  setup, governance state, rule-pack publication). Each must call
  ``services.self_audit.record_privileged`` / ``record_access`` (or the
  clients-router ``_log_event`` helper) in its handler.
* ``DATA_PLANE`` — per-request product actions performed by ordinary users
  (running a scan, ingesting a record, reading a notification). These are
  covered by their own evidence trails (TRACE chains, coverage checkpoints) and
  would drown the admin trail if mirrored into it. Each carries a reason.

Adding a route means adding it here. That is the point.
"""

from __future__ import annotations

# (METHOD, path) → action class recorded by the handler.
AUDITED: dict[tuple[str, str], str] = {
    # ── Tenancy & identity ──────────────────────────────────────────────────
    ("POST", "/api/v1/tenants"): "ADMIN_ACTION",
    ("POST", "/api/v1/clients"): "ADMIN_ACTION",
    ("POST", "/api/v1/clients/{tenant_id}/scim/rotate-token"): "ADMIN_ACTION",
    ("POST", "/api/v1/clients/{tenant_id}/test-sso"): "ADMIN_ACTION",
    ("PATCH", "/api/v1/auth/users/{user_id}/persona"): "ADMIN_ACTION",
    # ── Tenant configuration ────────────────────────────────────────────────
    ("PUT", "/api/v1/risk-config"): "ADMIN_ACTION",
    ("DELETE", "/api/v1/risk-config"): "ADMIN_ACTION",
    # ── Integration / adapter configuration ─────────────────────────────────
    ("POST", "/api/v1/github/configure"): "ADMIN_ACTION",
    ("DELETE", "/api/v1/github/disconnect"): "ADMIN_ACTION",
    ("POST", "/api/v1/github/scan-with-token/{audit_id}"): "ADMIN_ACTION",
    # ── Rule-pack publication (INV-7 lifecycle) ─────────────────────────────
    ("POST", "/api/v1/rules/versions"): "RULE_PACK_CHANGE",
    # ── Authentication (FND-065) ────────────────────────────────────────────
    # Both outcomes are recorded; failed attempts are the half that makes
    # credential stuffing visible.
    ("POST", "/api/v1/auth/token"): "AUTH_EVENT",
}

# Routes deliberately NOT mirrored into the admin trail, each with a reason.
DATA_PLANE: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/scan"): "product evaluation — evidence lives in the TRACE chain",
    ("POST", "/api/v1/scan/data"): "product evaluation — TRACE chain",
    ("POST", "/api/v1/ingest"): "observation ingest — coverage checkpoints are its trail",
    ("POST", "/api/v1/audit/output"): "output audit — TRACE chain",
    ("POST", "/api/v1/evaluations/ingest"): "evaluation ingest — evaluation records are the trail",
    ("POST", "/api/v1/evaluations/trigger"): "evaluation run — evaluation records are the trail",
    ("POST", "/api/v1/observation-coverage/checkpoint"): "coverage heartbeat — its own store",
    ("POST", "/api/v1/observation-coverage/detect-gaps"): "derived read-ish computation over coverage store",
    ("POST", "/api/v1/coverage/systems"): "coverage inventory upsert — coverage store is the trail",
    ("POST", "/api/v1/hf/process"): "batch processing job — job records are the trail",
    ("POST", "/api/v1/trace/{audit_id}/export"): "evidence export — EXPORT events recorded by the export service",
    ("POST", "/api/v1/trace/{audit_id}/verify"): "read-only chain verification, no state change",
    ("POST", "/api/v1/reports/{audit_id}/iso42001-annex"): "report generation from existing evidence",
    ("POST", "/api/v1/metering/statement"): "billing statement generation from meter records",
    ("PATCH", "/api/v1/notifications/{notification_id}/read"): "per-user UI state",
    ("POST", "/api/v1/notifications/read-all"): "per-user UI state",
    # FND-065 history: these three once claimed "auth events handled by the auth
    # path" — a mechanism that did not exist (CLAUDE.md FM-2). Login is now
    # genuinely audited and has moved to AUDITED above. Register and bootstrap
    # create users rather than sessions; their AUTH_EVENT coverage is still
    # outstanding and is stated as such rather than assumed.
    ("POST", "/api/v1/auth/register"): "user creation — AUTH_EVENT coverage still outstanding (FND-065)",
    ("POST", "/api/v1/auth/bootstrap"): "first-run bootstrap, self-disabling — AUTH_EVENT coverage still outstanding (FND-065)",
    ("POST", "/api/v1/sso/magic-link"): "auth request — SSO path has its own replay/signature controls",
    ("POST", "/api/v1/sso/acs/{tenant_slug}"): "IdP assertion consumption — SSO controls",
    ("GET", "/api/v1/remediation/oauth/jira/callback"): "OAuth redirect (see threat-model TM-F1)",
    ("POST", "/api/v1/demo/signup"): "public demo intake — not an admin action",
    ("PATCH", "/api/v1/demo/requests/{request_id}"): "demo-request triage — non-evidence workflow state",
    ("POST", "/api/v1/feedback"): "pilot feedback submission — user workflow, not an admin action (STORY-382)",
    ("PATCH", "/api/v1/feedback/{feedback_id}/triage"): "feedback triage — non-evidence workflow state (STORY-382)",
    ("GET", "/api/v1/demo/token"): "demo token issuance — feature-flagged demo path",
    # Governance / GRC workflow state — user-level compliance work, tracked by
    # each record's own lifecycle fields; promoting these to the admin trail is
    # a deliberate follow-on decision, not an oversight.
    ("POST", "/api/v1/aims/documents"): "AIMS document lifecycle — document record is the trail",
    ("POST", "/api/v1/aims/documents/{doc_id}/link/{audit_id}"): "document↔audit linkage record",
    ("DELETE", "/api/v1/aims/documents/{doc_id}/link/{audit_id}"): "document↔audit linkage record",
    ("PUT", "/api/v1/compliance/readiness/{item_key}"): "readiness checklist state",
    ("POST", "/api/v1/dispositions/bulk-acknowledge"): "disposition lifecycle — DISPOSITION_ACTION on the record itself",
    ("POST", "/api/v1/dispositions/expire-waivers"): "scheduled waiver expiry — disposition records",
    ("POST", "/api/v1/dispositions/{disp_id}/acknowledge"): "disposition lifecycle",
    ("POST", "/api/v1/dispositions/{disp_id}/escalate"): "disposition lifecycle",
    ("POST", "/api/v1/dispositions/{disp_id}/remediate"): "disposition lifecycle",
    ("POST", "/api/v1/dispositions/{disp_id}/waive"): "disposition lifecycle",
    ("POST", "/api/v1/grc/registry"): "GRC registry entry — entry audit endpoint is its trail",
    ("PATCH", "/api/v1/grc/registry/{entry_id}"): "GRC registry entry — entry audit endpoint is its trail",
    ("POST", "/api/v1/risks/bulk"): "risk register records",
    ("PATCH", "/api/v1/risks/{risk_id}"): "risk register records",
    ("DELETE", "/api/v1/risks/{risk_id}"): "risk register records",
    ("POST", "/api/v1/systems"): "AI system registry records",
    ("PATCH", "/api/v1/systems/{system_id}"): "AI system registry records",
    ("POST", "/api/v1/insights/{insight_id}/action"): "insight workflow state",
    ("POST", "/api/v1/remediation/steps"): "remediation workflow state",
    ("POST", "/api/v1/remediation/bulk-remediate"): "remediation workflow state",
    ("PATCH", "/api/v1/remediation/traces/{trace_id}/remediate"): "remediation workflow state",
    ("POST", "/api/v1/remediation/traces/{trace_id}/create-jira-issue"): "outbound ticket creation (read-only posture preserved)",
    ("POST", "/api/v1/traces/{audit_id}/{trace_id}/remediate"): "remediation workflow state",
    ("POST", "/api/v1/github/scan/{audit_id}"): "scan execution against configured integration",
    ("POST", "/api/v1/governance/erasure-request"): "DSR intake — erasure records are the trail",
    ("POST", "/api/v1/governance/retention-policy"): "retention policy record — policy table is versioned",
    # EVF / QCO governance chain — publications are already hash-chained
    # (routers/evf_sprint3.py verify-chain endpoint) which is a stronger,
    # purpose-built trail than the generic admin log.
    ("POST", "/api/v1/evf/engagements"): "EVF engagement record + transitions endpoint",
    ("POST", "/api/v1/evf/engagements/{engagement_id}/transition"): "EVF transitions are themselves the trail",
    ("PATCH", "/api/v1/evf/engagements/{engagement_id}/gate"): "EVF validation-gate record",
    ("POST", "/api/v1/evf/engagements/{engagement_id}/gate/lock"): "EVF validation-gate record",
    ("POST", "/api/v1/evf/qco"): "QCO registry record",
    ("PATCH", "/api/v1/evf/qco/{qco_id}"): "QCO registry record",
    ("POST", "/api/v1/evf/qco/{qco_id}/publish"): "QCO publication hash chain (verify-chain endpoint)",
    ("POST", "/api/v1/evf/qco/{qco_id}/renew"): "QCO registry record",
    ("POST", "/api/v1/evf/publications"): "publication hash chain",
    ("POST", "/api/v1/evf/admin/expiry-scan"): "scheduled scan — emits expiry alerts, no config change",
}


def classification(method: str, path: str) -> str | None:
    """Return 'AUDITED' | 'DATA_PLANE' | None (unclassified)."""
    key = (method.upper(), path)
    if key in AUDITED:
        return "AUDITED"
    if key in DATA_PLANE:
        return "DATA_PLANE"
    return None
