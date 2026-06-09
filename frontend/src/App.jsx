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
const DemoRequests  = lazy(() => import("./pages/DemoRequests"));
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
  demo_requests:    DemoRequests,
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
