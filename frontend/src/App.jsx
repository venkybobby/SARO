/**
 * App shell — full SARO React frontend with sidebar navigation.
 *
 * Auth token is persisted in localStorage so page refresh doesn't log out.
 * Sidebar navigation matches the Streamlit persona-based tab list exactly.
 *
 * Routes / pages:
 *   /login          → Login (unauthenticated)
 *   /demo           → DemoEntry (public)
 *   /app/*          → Authenticated app shell with sidebar
 */
import React, { useState, useEffect, Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login    from "./pages/Login";
import DemoEntry from "./pages/DemoEntry";
import Sidebar  from "./components/Sidebar";

// Lazy-load pages to keep initial bundle small
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

// Tab ID → component mapping
const PAGE_COMPONENTS = {
  dashboard:        Dashboard,
  compliance_hub:   ComplianceHub,
  trace_view:       TraceView,
  evidence_export:  TraceView,
  risk_summary:     RiskSummary,
  vendor_risk:      RiskSummary,
  claims_matrix:    ClaimsMatrix,
  how_saro_reasons: HowSaroReasons,
  dpa_governance:   GovernanceDocs,
  ir_plan:          GovernanceDocs,
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
    <div style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>Loading…</div>
  );
}

function AppShell({ token, user, onSignOut }) {
  const [activePage, setActivePage] = useState("dashboard");
  const tenantId = user?.tenant_id || parseJwt(token)?.tenant_id || parseJwt(token)?.sub;

  const PageComponent = PAGE_COMPONENTS[activePage] || Dashboard;

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", fontFamily: "system-ui, sans-serif" }}>
      <Sidebar
        user={user}
        activePage={activePage}
        onNavigate={setActivePage}
        onSignOut={onSignOut}
        token={token}
      />
      <main style={{ flex: 1, overflowY: "auto", background: "#f9fafb" }}>
        <Suspense fallback={<Loader />}>
          <PageComponent token={token} tenantId={tenantId} user={user} />
        </Suspense>
      </main>
    </div>
  );
}

export default function App() {
  const [token, setToken]   = useState(() => {
    const stored = localStorage.getItem(LS_TOKEN);
    return isTokenValid(stored) ? stored : null;
  });
  const [user, setUser]     = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_USER) || "null"); } catch { return null; }
  });
  const [expired, setExpired] = useState(false);

  // Check token expiry on mount and every minute
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
  }

  function handleSignOut() {
    setToken(null);
    setUser(null);
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
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
              ? <AppShell token={token} user={user} onSignOut={handleSignOut} />
              : <Navigate to="/login" replace />
          }
        />
        {/* Legacy /dashboard route — redirect to /app */}
        <Route path="/dashboard" element={<Navigate to="/app" replace />} />
        <Route path="/" element={<Navigate to={isAuth ? "/app" : "/login"} replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
