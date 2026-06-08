/**
 * Sidebar — persona-aware navigation mirroring the Streamlit sidebar.
 * Reads persona from props, renders filtered tab list, health indicator.
 */
import React, { useEffect, useState } from "react";

const PERSONA_TABS = {
  compliance_lead: [
    "dashboard", "compliance_hub", "trace_view", "evidence_export",
    "claims_matrix", "how_saro_reasons", "dpa_governance",
    "aims", "governance", "onboarding", "upload", "evaluations",
  ],
  risk_officer: [
    "dashboard", "risk_summary", "vendor_risk", "ir_plan", "trace_view",
  ],
  ai_auditor: [
    "dashboard", "trace_view", "evidence_export",
    "rule_packs", "coverage_gap", "remediation", "drift_alerts", "upload",
  ],
  admin: [
    "dashboard", "compliance_hub", "trace_view", "evidence_export",
    "risk_summary", "vendor_risk", "claims_matrix", "how_saro_reasons",
    "dpa_governance", "rule_packs", "coverage_gap", "remediation",
    "drift_alerts", "aims", "governance", "onboarding", "upload",
    "admin_settings", "evaluations", "evf_admin", "demo_requests",
  ],
  super_admin: [
    "dashboard", "compliance_hub", "trace_view", "evidence_export",
    "risk_summary", "vendor_risk", "claims_matrix", "how_saro_reasons",
    "dpa_governance", "rule_packs", "coverage_gap", "remediation",
    "drift_alerts", "aims", "governance", "onboarding", "upload",
    "admin_settings", "evaluations", "demo_requests",
  ],
  operator: ["dashboard", "upload", "trace_view", "remediation"],
};

const TAB_REGISTRY = {
  dashboard:       { label: "🏠 Dashboard",           page: "dashboard" },
  compliance_hub:  { label: "🏛️ Compliance Hub",      page: "compliance_hub" },
  trace_view:      { label: "🔍 TRACE View",           page: "trace_view" },
  evidence_export: { label: "📦 Evidence Export",      page: "trace_view" },
  risk_summary:    { label: "📊 Risk Summary",         page: "risk_summary" },
  vendor_risk:     { label: "🏢 Vendor Risk",          page: "risk_summary" },
  claims_matrix:   { label: "📋 Claims Matrix",        page: "claims_matrix" },
  how_saro_reasons:{ label: "💡 How SARO Reasons",     page: "how_saro_reasons" },
  dpa_governance:  { label: "📄 DPA & Governance",     page: "governance_docs" },
  ir_plan:         { label: "🚨 IR Plan",              page: "governance_docs" },
  rule_packs:      { label: "📦 Rule Packs",           page: "rule_packs" },
  coverage_gap:    { label: "🗺️ Coverage Gap",         page: "coverage_gap" },
  remediation:     { label: "🔧 Remediation",          page: "remediation" },
  drift_alerts:    { label: "📡 Drift Alerts",         page: "drift_alerts" },
  onboarding:      { label: "🏢 Onboarding",           page: "onboarding" },
  upload:          { label: "📤 Upload & Scan",        page: "upload" },
  admin_settings:  { label: "⚙️ Admin Settings",       page: "admin_settings" },
  aims:            { label: "📋 AIMS",                 page: "aims" },
  governance:      { label: "🏛️ Governance Trust",    page: "governance" },
  evaluations:     { label: "🧪 Evaluations",          page: "evaluations" },
  evf_admin:       { label: "🔐 EVF Status",           page: "evf_admin" },
  demo_requests:   { label: "📋 Demo Requests",        page: "demo_requests" },
};

const PERSONA_ICONS = {
  compliance_lead: "⚖️",
  risk_officer: "📊",
  ai_auditor: "🔍",
  admin: "⚙️",
  super_admin: "⚙️",
  operator: "👤",
};

const PERSONA_LABELS = {
  compliance_lead: "Compliance Lead",
  risk_officer: "Risk Officer",
  ai_auditor: "AI Auditor",
  admin: "Admin",
  super_admin: "Super Admin",
  operator: "Operator",
};

const S = {
  sidebar: {
    width: 240,
    background: "#0f172a",
    color: "#e2e8f0",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    padding: "16px 0",
    flexShrink: 0,
    overflowY: "auto",
  },
  logo: { padding: "0 16px 12px", borderBottom: "1px solid #1e293b" },
  logoTitle: { fontWeight: 700, fontSize: 16, color: "#f1f5f9" },
  logoSub: { fontSize: 10, color: "#475569", letterSpacing: "0.06em", textTransform: "uppercase" },
  userBlock: { padding: "12px 16px", borderBottom: "1px solid #1e293b" },
  userLabel: { fontSize: 10, color: "#475569", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600, marginBottom: 3 },
  userEmail: { fontSize: 13, color: "#e2e8f0", fontWeight: 500, wordBreak: "break-all" },
  badge: (bg, color) => ({
    display: "inline-block", background: bg, color, padding: "2px 8px",
    borderRadius: 4, fontSize: 11, fontWeight: 600, marginTop: 4,
  }),
  health: { padding: "8px 16px", borderBottom: "1px solid #1e293b", fontSize: 12, color: "#475569" },
  navSection: { flex: 1, padding: "8px 0" },
  navItem: (active) => ({
    display: "block", width: "100%", textAlign: "left",
    padding: "8px 16px", background: active ? "#1e293b" : "transparent",
    color: active ? "#f1f5f9" : "#94a3b8", border: "none",
    fontSize: 13, cursor: "pointer", transition: "all 0.15s",
    borderLeft: active ? "3px solid #0d9488" : "3px solid transparent",
  }),
  signout: {
    padding: "12px 16px", borderTop: "1px solid #1e293b", marginTop: "auto",
  },
  signoutBtn: {
    width: "100%", padding: "8px 0", background: "#1e293b", color: "#94a3b8",
    border: "1px solid #334155", borderRadius: 6, fontSize: 13, cursor: "pointer",
  },
  version: { fontSize: 10, color: "#334155", textAlign: "center", padding: "8px 16px 0" },
};

export default function Sidebar({ user, activePage, onNavigate, onSignOut, token }) {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch("/api/v1/../health");
        if (r.ok) setHealth(await r.json());
        else setHealth(null);
      } catch {
        setHealth(null);
      }
    };
    check();
    const t = setInterval(check, 30000);
    return () => clearInterval(t);
  }, []);

  const persona = user?.persona_role || user?.role || "operator";
  const allowedTabIds = PERSONA_TABS[persona] || PERSONA_TABS.operator;
  const seen = new Set();
  const tabs = allowedTabIds.filter((id) => {
    if (seen.has(id) || !TAB_REGISTRY[id]) return false;
    seen.add(id);
    return true;
  });

  return (
    <div style={S.sidebar}>
      {/* Logo */}
      <div style={S.logo}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 20 }}>🛡️</span>
          <div>
            <div style={S.logoTitle}>SARO</div>
            <div style={S.logoSub}>Smart AI Risk Orchestrator</div>
          </div>
        </div>
      </div>

      {/* User block */}
      <div style={S.userBlock}>
        <div style={S.userLabel}>Signed in as</div>
        <div style={S.userEmail}>{user?.email}</div>
        <div>
          <span style={S.badge("#1e3a5f", "#60a5fa")}>
            {user?.role?.replace("_", " ") || ""}
          </span>
          {persona && PERSONA_LABELS[persona] && persona !== user?.role && (
            <span style={{ ...S.badge("#14532d", "#86efac"), marginLeft: 4 }}>
              {PERSONA_ICONS[persona]} {PERSONA_LABELS[persona]}
            </span>
          )}
        </div>
      </div>

      {/* Health */}
      <div style={S.health}>
        {health ? (
          <>
            <span style={{ color: "#4ade80" }}>● API online</span>
            {"  "}
            <span style={{ color: health.db_ok ? "#4ade80" : "#f87171" }}>
              ● DB {health.db_ok ? "ok" : "error"}
            </span>
          </>
        ) : (
          <span style={{ color: "#f87171" }}>● API offline</span>
        )}
      </div>

      {/* Nav */}
      <nav style={S.navSection}>
        {tabs.map((tabId) => {
          const { label, page } = TAB_REGISTRY[tabId];
          const active = activePage === page || (activePage === page && tabId === activePage);
          return (
            <button
              key={tabId}
              style={S.navItem(activePage === tabId)}
              onClick={() => onNavigate(tabId)}
            >
              {label}
            </button>
          );
        })}
      </nav>

      {/* Sign out */}
      <div style={S.signout}>
        <button style={S.signoutBtn} onClick={onSignOut}>
          Sign Out
        </button>
        <div style={S.version}>SARO v8.0.0 — Enterprise AI Governance</div>
      </div>
    </div>
  );
}
