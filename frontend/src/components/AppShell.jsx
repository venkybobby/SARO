/**
 * App shell — sidebar navigation + routed page content. Shared by the
 * authenticated /app route (App.jsx) and the public /demo route
 * (pages/DemoEntry.jsx) so both get identical navigation chrome; the demo
 * session is distinguished purely by the `user.role === "demo_viewer"` it
 * passes in, which Sidebar uses to render the DEMO_TABS whitelist (STORY-412).
 */
import React, { useState, useEffect, useCallback, Suspense, lazy } from "react";
import Sidebar from "./Sidebar";
import { ConfirmDialog } from "./ui/index.jsx";
import { useDirtyNavGuard } from "../hooks/useDirtyNavGuard.js";
import { TRACE_METHODOLOGY_READY } from "../config/traceGate";
import { parseJwt } from "../utils/jwt.js";
import DEMO_TABS from "../config/demoTabs.json";
import { ONBOARDING_STEP_NAV } from "../config/onboardingNav.js";

// Lazy-load pages
const Dashboard     = lazy(() => import("../pages/Dashboard"));
const ComplianceHub = lazy(() => import("../pages/ComplianceHub"));
const TraceView     = lazy(() => import("../pages/TraceView"));
// STORY-113: RiskSummary is no longer a standalone page — it is rendered as a
// collapsible band inside RiskRegister, which imports it directly.
// STORY-112: Governance, HowSaroReasons, ClaimsMatrix and GovernanceDocs are
// consolidated into the Trust Center, which imports them as tabbed sections.
const TrustCenter   = lazy(() => import("../pages/TrustCenter"));
const RulePacks     = lazy(() => import("../pages/RulePacks"));
// STORY-TAB-008: CoverageGap, Remediation, DriftAlerts, Onboarding and
// Evaluations are no longer routed pages — their hosts (ComplianceHub,
// TraceView, RulePacks, Dashboard, AdminSettings) import them directly.
const Aims          = lazy(() => import("../pages/Aims"));
const Upload        = lazy(() => import("../pages/Upload"));
const EvfAdmin      = lazy(() => import("../pages/EvfAdmin"));
const AdminSettings = lazy(() => import("../pages/AdminSettings"));
// DemoRequests removed — STORY-016: page deprecated, entry points already removed from nav
const RiskRegister    = lazy(() => import("../pages/RiskRegister"));
const RiskForm        = lazy(() => import("../pages/RiskForm"));
const RiskDetail      = lazy(() => import("../pages/RiskDetail"));
const KnowledgePortal = lazy(() => import("../pages/KnowledgePortal"));
const AIInsights      = lazy(() => import("../pages/AIInsights"));
const Reports         = lazy(() => import("../pages/Reports"));
const Settings        = lazy(() => import("../pages/Settings"));
const AuditTrail      = lazy(() => import("../pages/AuditTrail"));

const PAGE_COMPONENTS = {
  dashboard:        Dashboard,
  compliance_hub:   ComplianceHub,
  trace_view:       TraceView,
  // STORY-113: risk_summary merged into Risk Register; redirect any lingering
  // nav/deep-link here so it never falls through to Dashboard (FND-007).
  risk_summary:     RiskRegister,
  risk_register:    RiskRegister,
  // STORY-112: the four governance pages now resolve to the Trust Center. The
  // old keys are kept as redirects (with initialTab) so deep-links/aliases don't
  // fall through to Dashboard (FND-007).
  trust_center:     TrustCenter,
  claims_matrix:    TrustCenter,
  how_saro_reasons: TrustCenter,
  dpa_governance:   TrustCenter,
  governance_docs:  TrustCenter,
  rule_packs:       RulePacks,
  // STORY-TAB-008: the five consolidated pages are no longer standalone routes.
  // Old keys redirect to the HOST page (FND-007 discipline: a navigated key
  // must never silently fall through to Dashboard).
  coverage_gap:     ComplianceHub,
  remediation:      TraceView,
  drift_alerts:     RulePacks,
  aims:             Aims,
  governance:       TrustCenter,
  onboarding:       Dashboard,
  upload:           Upload,
  evaluations:      AdminSettings,
  evf_admin:        EvfAdmin,
  admin_settings:   AdminSettings,
  // demo_requests removed — STORY-016
  // FND-007: risk_detail was navigated to (RiskRegister, AIInsights) but never
  // registered here, so it silently fell through to Dashboard.
  risk_detail:      RiskDetail,
  ai_insights:      AIInsights,
  reports:          Reports,
  settings:         Settings,
  audit_trail:      AuditTrail,
};

const LS_ONBOARDING_DISMISSED = "saro_onboarding_dismissed";

function Loader() {
  return (
    <div style={{
      padding: 40, textAlign: "center",
      color: "var(--color-text-muted)",
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
    }}>
      Loading…
    </div>
  );
}

// STORY-TAB-002 / FND-075: the wizard renders the backend checklist verbatim
// (routers/onboarding.py returns {steps:[{key,label,completed}], completed_steps,
// total_steps, completion_pct}); it previously hardcoded 7 divergent step ids
// and read flat booleans, so every first login showed 0/7.
function OnboardingWizard({ token, tenantId, onDismiss, onNavigate }) {
  const [status, setStatus] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const url = `/api/v1/onboarding/status${tenantId ? `?tenant_id=${tenantId}` : ""}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => { setStatus(d); setFailed(false); })
      .catch(() => setFailed(true));
  }, [token, tenantId]);

  const steps = status?.steps || [];
  const completed = status?.completed_steps ?? 0;
  const totalSteps = status?.total_steps ?? steps.length;
  const pct = status?.completion_pct ?? 0;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: "var(--color-bg-surface)", borderRadius: 12,
        width: "100%", maxWidth: 520, maxHeight: "90vh", overflowY: "auto",
        boxShadow: "0 20px 60px rgba(0,0,0,0.35)",
        border: "1px solid var(--color-border-subtle)",
      }}>
        {/* Header */}
        <div style={{ padding: "20px 24px 16px", borderBottom: "1px solid var(--color-border-subtle)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--color-text-primary)", fontFamily: "var(--font-display)" }}>
              Welcome to SARO
            </div>
            <button onClick={onDismiss} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-text-muted)", fontSize: 20, lineHeight: 1 }}>×</button>
          </div>
          <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 12 }}>
            Complete these steps to get fully operational. You can revisit this checklist any time from Settings.
          </div>
          {!failed && (
            <>
              <div style={{ height: 6, background: "var(--color-bg-elevated)", borderRadius: 3 }}>
                <div style={{ height: 6, width: `${pct}%`, background: "var(--color-info)", borderRadius: 3, transition: "width 0.4s" }} />
              </div>
              <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
                {completed}/{totalSteps} steps complete
              </div>
            </>
          )}
          {failed && (
            <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
              Couldn't load setup progress — you can revisit this checklist from the Onboarding tab.
            </div>
          )}
        </div>

        {/* Steps — rendered from the API checklist */}
        <div style={{ padding: "12px 24px" }}>
          {steps.map((s, i) => {
            const done = !!s.completed;
            const navTarget = ONBOARDING_STEP_NAV[s.key];
            return (
              <div key={s.key} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
                borderBottom: i < steps.length - 1 ? "1px solid var(--color-border-subtle)" : "none",
              }}>
                <div style={{
                  width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
                  background: done ? "var(--color-info)" : "var(--color-bg-elevated)",
                  border: `1px solid ${done ? "var(--color-info)" : "var(--color-border-default)"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 12, color: done ? "#fff" : "var(--color-text-muted)", fontWeight: 700,
                }}>
                  {done ? "✓" : i + 1}
                </div>
                <span style={{ flex: 1, fontSize: 13, color: done ? "var(--color-text-muted)" : "var(--color-text-primary)" }}>
                  {s.label}
                  {done && <span style={{ marginLeft: 6, fontSize: 11, color: "var(--color-info)" }}>Done</span>}
                </span>
                {!done && navTarget && (
                  <button onClick={() => { onNavigate?.(navTarget); onDismiss(); }} style={{
                    padding: "4px 10px", background: "var(--color-info-bg)", color: "var(--color-info)",
                    border: "1px solid var(--color-info-border)", borderRadius: 5,
                    cursor: "pointer", fontSize: 11, fontWeight: 600,
                  }}>
                    Go →
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{ padding: "12px 24px 20px", borderTop: "1px solid var(--color-border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {pct === 100 ? (
            <span style={{ fontSize: 13, color: "var(--color-info)", fontWeight: 600 }}>🎉 Setup complete!</span>
          ) : (
            <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>You can dismiss this and return to it later via Settings.</span>
          )}
          <button onClick={onDismiss} style={{
            padding: "7px 16px", background: "var(--color-info)", color: "#fff",
            border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13, fontWeight: 600,
          }}>
            {pct === 100 ? "Finish" : "Continue to App →"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AppShell({ token, user, onSignOut, onUserUpdate, toast }) {
  const [activePage, setActivePage] = useState("dashboard");
  const [navPayload, setNavPayload] = useState(null);
  const tenantId = user?.tenant_id || parseJwt(token)?.tenant_id || parseJwt(token)?.sub;

  // Show onboarding wizard only on first-ever login (admin/super_admin) if not yet dismissed
  const showWizardForPersona = ["admin","super_admin"].includes(user?.persona_role || user?.role);
  const [showOnboarding, setShowOnboarding] = useState(
    showWizardForPersona && !localStorage.getItem(LS_ONBOARDING_DISMISSED)
  );

  const PageComponent = PAGE_COMPONENTS[activePage] || Dashboard;

  // STORY-412: DEMO_TABS trims Sidebar's own button list, but any page can still
  // call onNavigate(page) directly (e.g. TraceView's "How SARO Reasons" link).
  // The real enforcement has to live here, at the one place all navigation flows
  // through — otherwise an off-whitelist page renders and 403s on its own fetches.
  const isDemo = user?.role === "demo_viewer";

  const navigateNow = useCallback((page, payload) => {
    if (isDemo && !DEMO_TABS.includes(page)) return;
    setActivePage(page);
    setNavPayload(payload || null);
  }, [isDemo]);

  const { pendingNav, registerDirtyGuard, handleNavigate, confirmNav, cancelNav } = useDirtyNavGuard(navigateNow);

  function dismissOnboarding() {
    localStorage.setItem(LS_ONBOARDING_DISMISSED, "1");
    setShowOnboarding(false);
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      {showOnboarding && (
        <OnboardingWizard
          token={token}
          tenantId={tenantId}
          onDismiss={dismissOnboarding}
          onNavigate={handleNavigate}
        />
      )}
      <Sidebar
        user={user}
        activePage={activePage}
        onNavigate={handleNavigate}
        onSignOut={onSignOut}
        onUserUpdate={onUserUpdate}
        token={token}
      />
      <main
        id="main-content"
        style={{ flex: 1, overflowY: "auto", background: "var(--color-bg-base)" }}
      >
        <Suspense fallback={<Loader />}>
          <PageComponent
            token={token}
            tenantId={tenantId}
            user={user}
            toast={toast}
            onNavigate={handleNavigate}
            onRegisterDirtyGuard={registerDirtyGuard}
            onSave={() => toast.success("Settings saved")}
            initialAuditId={activePage === "trace_view" ? navPayload : undefined}
            methodologyReady={TRACE_METHODOLOGY_READY}
            initialRiskId={activePage === "ai_insights" ? navPayload : undefined}
            riskId={
              activePage === "risk_detail"
                ? (typeof navPayload === "object" && navPayload !== null ? navPayload.riskId : navPayload)
                : undefined
            }
            suggestedRemediation={
              activePage === "risk_detail" && typeof navPayload === "object" && navPayload !== null
                ? navPayload.suggestedRemediation
                : undefined
            }
            initialSection={
              activePage === "claims_matrix" && typeof navPayload === "object" && navPayload !== null
                ? navPayload.section
                : undefined
            }
            initialTab={
              ["governance", "how_saro_reasons", "claims_matrix", "dpa_governance"].includes(activePage)
                ? activePage
                : activePage === "governance_docs"
                  ? "dpa_governance"
                  : undefined
            }
          />
        </Suspense>
      </main>

      <ConfirmDialog
        open={!!pendingNav}
        title="Discard unsaved changes?"
        description="You have unsaved changes. If you leave now, your edits will be lost."
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        onConfirm={confirmNav}
        onCancel={cancelNav}
      />

      <VersionFooter />
    </div>
  );
}

// STORY-375: surface the running platform version. Read from GET /api/v1/version
// (the single source), so the footer cannot drift from what is actually
// deployed. Renders nothing until the version is known — a blank footer is
// better than a stale or guessed version number.
function VersionFooter() {
  const [info, setInfo] = React.useState(null);
  React.useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/version")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled) setInfo(d);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  if (!info?.version) return null;
  return (
    <footer
      style={{
        padding: "0.5rem 1rem",
        fontSize: "0.75rem",
        opacity: 0.6,
        textAlign: "center",
      }}
    >
      SARO v{info.version}
      {info.commit && info.commit !== "unknown" ? ` · ${info.commit.slice(0, 7)}` : ""}
    </footer>
  );
}
