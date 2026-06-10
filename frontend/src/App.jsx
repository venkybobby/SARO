/**
 * App shell — full SARO React frontend with sidebar navigation.
 *
 * Auth token is persisted in localStorage so page refresh doesn't log out.
 * Sidebar navigation matches the Streamlit persona-based tab list exactly.
 */
import React, { useState, useEffect, Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login    from "./pages/Login";
import DemoEntry from "./pages/DemoEntry";
import Sidebar  from "./components/Sidebar";
import { ToastContainer } from "./components/ui/index.jsx";
import { useToast } from "./hooks/useToast.js";

// Lazy-load pages
const Dashboard     = lazy(() => import("./pages/Dashboard"));
const ComplianceHub = lazy(() => import("./pages/ComplianceHub"));
const TraceView     = lazy(() => import("./pages/TraceView"));
const RiskSummary   = lazy(() => import("./pages/RiskSummary"));
const ClaimsMatrix  = lazy(() => import("./pages/ClaimsMatrix"));
const HowSaroReasons= lazy(() => import("./pages/HowSaroReasons"));
const GovernanceDocs= lazy(() => import("./pages/GovernanceDocs"));
const RulePacks     = lazy(() => import("./pages/RulePacks"));
const CoverageGap   = lazy(() => import("./pages/CoverageGap"));
const Remediation   = lazy(() => import("./pages/Remediation"));
const DriftAlerts   = lazy(() => import("./pages/DriftAlerts"));
const Aims          = lazy(() => import("./pages/Aims"));
const Governance    = lazy(() => import("./pages/Governance"));
const Onboarding    = lazy(() => import("./pages/Onboarding"));
const Upload        = lazy(() => import("./pages/Upload"));
const Evaluations   = lazy(() => import("./pages/Evaluations"));
const EvfAdmin      = lazy(() => import("./pages/EvfAdmin"));
const AdminSettings = lazy(() => import("./pages/AdminSettings"));
// DemoRequests removed — STORY-016: page deprecated, entry points already removed from nav
const RiskRegister    = lazy(() => import("./pages/RiskRegister"));
const RiskForm        = lazy(() => import("./pages/RiskForm"));
const RiskDetail      = lazy(() => import("./pages/RiskDetail"));
const KnowledgePortal = lazy(() => import("./pages/KnowledgePortal"));
const AIInsights      = lazy(() => import("./pages/AIInsights"));
const Reports         = lazy(() => import("./pages/Reports"));
const Settings        = lazy(() => import("./pages/Settings"));

const PAGE_COMPONENTS = {
  dashboard:        Dashboard,
  compliance_hub:   ComplianceHub,
  trace_view:       TraceView,
  risk_summary:     RiskSummary,
  risk_register:    RiskRegister,
  claims_matrix:    ClaimsMatrix,
  how_saro_reasons: HowSaroReasons,
  dpa_governance:   GovernanceDocs,
  rule_packs:       RulePacks,
  coverage_gap:     CoverageGap,
  remediation:      Remediation,
  drift_alerts:     DriftAlerts,
  aims:             Aims,
  governance:       Governance,
  onboarding:       Onboarding,
  upload:           Upload,
  evaluations:      Evaluations,
  evf_admin:        EvfAdmin,
  admin_settings:   AdminSettings,
  // demo_requests removed — STORY-016
  ai_insights:      AIInsights,
  reports:          Reports,
  settings:         Settings,
};

function parseJwt(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return {};
  }
}

function isTokenValid(token) {
  if (!token) return false;
  try {
    const payload = parseJwt(token);
    return Date.now() / 1000 < (payload.exp || 0) - 60;
  } catch {
    return false;
  }
}

const LS_TOKEN = "saro_token";
const LS_USER  = "saro_user";
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

const ONBOARDING_STEPS = [
  { id: "tenant_created",     label: "Tenant Created" },
  { id: "users_invited",      label: "Users Invited" },
  { id: "personas_assigned",  label: "Personas Assigned" },
  { id: "first_scan",         label: "First Scan Completed" },
  { id: "rule_packs_reviewed",label: "Rule Packs Reviewed" },
  { id: "integrations",       label: "Integrations Configured" },
  { id: "compliance_review",  label: "Compliance Review Booked" },
];

function OnboardingWizard({ token, tenantId, onDismiss, onNavigate }) {
  const [progress, setProgress] = useState({});

  useEffect(() => {
    const url = `/api/v1/onboarding/status${tenantId ? `?tenant_id=${tenantId}` : ""}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : {})
      .then(setProgress)
      .catch(() => {});
  }, [token, tenantId]);

  const completed = ONBOARDING_STEPS.filter((s) => progress[s.id]).length;
  const pct = Math.round((completed / ONBOARDING_STEPS.length) * 100);

  const STEP_ACTIONS = {
    first_scan:   () => onNavigate?.("upload"),
    rule_packs_reviewed: () => onNavigate?.("rule_packs"),
    personas_assigned: () => onNavigate?.("admin_settings"),
  };

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
          <div style={{ height: 6, background: "var(--color-bg-elevated)", borderRadius: 3 }}>
            <div style={{ height: 6, width: `${pct}%`, background: "var(--color-info)", borderRadius: 3, transition: "width 0.4s" }} />
          </div>
          <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 4 }}>
            {completed}/{ONBOARDING_STEPS.length} steps complete
          </div>
        </div>

        {/* Steps */}
        <div style={{ padding: "12px 24px" }}>
          {ONBOARDING_STEPS.map((s, i) => {
            const done = !!progress[s.id];
            const action = STEP_ACTIONS[s.id];
            return (
              <div key={s.id} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
                borderBottom: i < ONBOARDING_STEPS.length - 1 ? "1px solid var(--color-border-subtle)" : "none",
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
                {!done && action && (
                  <button onClick={() => { action(); onDismiss(); }} style={{
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

function AppShell({ token, user, onSignOut, onUserUpdate, toast }) {
  const [activePage, setActivePage] = useState("dashboard");
  const [navPayload, setNavPayload] = useState(null);
  const tenantId = user?.tenant_id || parseJwt(token)?.tenant_id || parseJwt(token)?.sub;

  // Show onboarding wizard only on first-ever login (admin/super_admin) if not yet dismissed
  const showWizardForPersona = ["admin","super_admin"].includes(user?.persona_role || user?.role);
  const [showOnboarding, setShowOnboarding] = useState(
    showWizardForPersona && !localStorage.getItem(LS_ONBOARDING_DISMISSED)
  );

  const PageComponent = PAGE_COMPONENTS[activePage] || Dashboard;

  function handleNavigate(page, payload) {
    setActivePage(page);
    setNavPayload(payload || null);
  }

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
            onSave={() => toast.success("Settings saved")}
            initialAuditId={activePage === "trace_view" ? navPayload : undefined}
          />
        </Suspense>
      </main>
    </div>
  );
}

export default function App() {
  const { toasts, dismiss, toast } = useToast();

  const [token, setToken] = useState(() => {
    const stored = localStorage.getItem(LS_TOKEN);
    return isTokenValid(stored) ? stored : null;
  });
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_USER) || "null"); } catch { return null; }
  });
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    const check = () => {
      if (token && !isTokenValid(token)) {
        setExpired(true);
        setToken(null);
        setUser(null);
        localStorage.removeItem(LS_TOKEN);
        localStorage.removeItem(LS_USER);
      }
    };
    check();
    const t = setInterval(check, 60000);
    return () => clearInterval(t);
  }, [token]);

  function handleLogin(newToken, userPayload) {
    setToken(newToken);
    setUser(userPayload);
    setExpired(false);
    localStorage.setItem(LS_TOKEN, newToken);
    localStorage.setItem(LS_USER, JSON.stringify(userPayload));
    toast.success("Signed in successfully");
  }

  function handleSignOut() {
    setToken(null);
    setUser(null);
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
  }

  function handleUserUpdate(updatedUser) {
    setUser(updatedUser);
    localStorage.setItem(LS_USER, JSON.stringify(updatedUser));
  }

  const isAuth = token && isTokenValid(token);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/demo" element={<DemoEntry />} />
        <Route
          path="/login"
          element={
            isAuth
              ? <Navigate to="/app" replace />
              : <Login onLogin={handleLogin} sessionExpired={expired} />
          }
        />
        <Route
          path="/app"
          element={
            isAuth
              ? <AppShell token={token} user={user} onSignOut={handleSignOut} onUserUpdate={handleUserUpdate} toast={toast} />
              : <Navigate to="/login" replace />
          }
        />
        <Route path="/dashboard" element={<Navigate to="/app" replace />} />
        <Route path="/" element={<Navigate to={isAuth ? "/app" : "/login"} replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </BrowserRouter>
  );
}
