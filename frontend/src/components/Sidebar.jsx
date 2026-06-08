import React, { useEffect, useState } from "react";
import {
  LayoutDashboard, Shield, Search, Package, BarChart2,
  Map, Wrench, Activity, Building2, Upload, Settings,
  ClipboardList, BookOpen, Users, Lightbulb, FileText,
  AlertTriangle, Lock, ShieldCheck, LogOut, ChevronRight,
  ShieldAlert, Sparkles, LineChart,
} from "lucide-react";
import { StatusDot } from "./ui/index.jsx";

const PERSONA_TABS = {
  compliance_lead: [
    "dashboard","compliance_hub","trace_view","evidence_export",
    "claims_matrix","how_saro_reasons","dpa_governance",
    "aims","governance","onboarding","upload","evaluations",
  ],
  risk_officer: ["dashboard","risk_register","risk_summary","vendor_risk","ir_plan","trace_view","ai_insights","reports"],
  ai_auditor: [
    "dashboard","trace_view","evidence_export",
    "rule_packs","coverage_gap","remediation","drift_alerts","upload",
  ],
  admin: [
    "dashboard","compliance_hub","trace_view","evidence_export",
    "risk_summary","vendor_risk","claims_matrix","how_saro_reasons",
    "dpa_governance","rule_packs","coverage_gap","remediation",
    "drift_alerts","aims","governance","onboarding","upload",
    "admin_settings","evaluations","evf_admin","demo_requests",
    "risk_register","ai_insights","reports","settings",
  ],
  super_admin: [
    "dashboard","compliance_hub","trace_view","evidence_export",
    "risk_summary","vendor_risk","claims_matrix","how_saro_reasons",
    "dpa_governance","rule_packs","coverage_gap","remediation",
    "drift_alerts","aims","governance","onboarding","upload",
    "admin_settings","evaluations","demo_requests",
  ],
  operator: ["dashboard","upload","trace_view","remediation"],
};

const TAB_REGISTRY = {
  dashboard:        { label: "Dashboard",         icon: LayoutDashboard, page: "dashboard" },
  compliance_hub:   { label: "Compliance Hub",    icon: Shield,          page: "compliance_hub" },
  trace_view:       { label: "TRACE View",         icon: Search,          page: "trace_view" },
  evidence_export:  { label: "Evidence Export",    icon: Package,         page: "trace_view" },
  risk_summary:     { label: "Risk Summary",       icon: BarChart2,       page: "risk_summary" },
  vendor_risk:      { label: "Vendor Risk",        icon: Building2,       page: "risk_summary" },
  claims_matrix:    { label: "Claims Matrix",      icon: ClipboardList,   page: "claims_matrix" },
  how_saro_reasons: { label: "How SARO Reasons",  icon: Lightbulb,       page: "how_saro_reasons" },
  dpa_governance:   { label: "DPA & Governance",   icon: FileText,        page: "governance_docs" },
  ir_plan:          { label: "IR Plan",            icon: AlertTriangle,   page: "governance_docs" },
  rule_packs:       { label: "Rule Packs",         icon: Package,         page: "rule_packs" },
  coverage_gap:     { label: "Coverage Gap",       icon: Map,             page: "coverage_gap" },
  remediation:      { label: "Remediation",        icon: Wrench,          page: "remediation" },
  drift_alerts:     { label: "Drift Alerts",       icon: Activity,        page: "drift_alerts" },
  onboarding:       { label: "Onboarding",         icon: Building2,       page: "onboarding" },
  upload:           { label: "Upload & Scan",      icon: Upload,          page: "upload" },
  admin_settings:   { label: "Admin Settings",     icon: Settings,        page: "admin_settings" },
  aims:             { label: "AIMS",               icon: ClipboardList,   page: "aims" },
  governance:       { label: "Governance Trust",   icon: ShieldCheck,     page: "governance" },
  evaluations:      { label: "Evaluations",        icon: BookOpen,        page: "evaluations" },
  evf_admin:        { label: "EVF Status",         icon: Lock,            page: "evf_admin" },
  demo_requests:    { label: "Demo Requests",      icon: Users,           page: "demo_requests" },
  risk_register:    { label: "Risk Register",      icon: ShieldAlert,     page: "risk_register" },
  ai_insights:      { label: "AI Insights",        icon: Sparkles,        page: "ai_insights" },
  reports:          { label: "Reports",            icon: LineChart,       page: "reports" },
  settings:         { label: "Settings",           icon: Settings,        page: "settings" },
};

const ROLE_LABELS = {
  compliance_lead: "Compliance Lead",
  risk_officer:    "Risk Officer",
  ai_auditor:      "AI Auditor",
  admin:           "Admin",
  super_admin:     "Super Admin",
  operator:        "Operator",
};

export default function Sidebar({ user, activePage, onNavigate, onSignOut }) {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch("/health");
        setHealth(r.ok ? await r.json() : null);
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

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "??";

  return (
    <nav
      aria-label="Main navigation"
      style={{
        width: 240, flexShrink: 0,
        background: "var(--color-bg-surface)",
        borderRight: "1px solid var(--color-border-subtle)",
        height: "100vh", display: "flex", flexDirection: "column",
        overflowY: "auto",
      }}
    >
      {/* Logo */}
      <div style={{
        padding: "var(--space-4) var(--space-4) var(--space-3)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "center", gap: "var(--space-3)",
      }}>
        <Shield size={22} color="var(--color-info)" strokeWidth={2} />
        <div>
          <div style={{
            fontFamily: "var(--font-display)", fontWeight: "var(--weight-semibold)",
            fontSize: "var(--text-md)", color: "var(--color-text-primary)",
            lineHeight: 1.2,
          }}>
            SARO
          </div>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
            letterSpacing: "0.05em", textTransform: "uppercase",
          }}>
            AI Risk Orchestrator
          </div>
        </div>
      </div>

      {/* User block */}
      <div style={{
        padding: "var(--space-3) var(--space-4)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "center", gap: "var(--space-3)",
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: "50%",
          background: "var(--color-info-bg)",
          border: "1px solid var(--color-info-border)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
          color: "var(--color-info)", flexShrink: 0,
        }}>
          {initials}
        </div>
        <div style={{ overflow: "hidden" }}>
          <div style={{
            fontSize: "var(--text-sm)", color: "var(--color-text-primary)",
            fontWeight: "var(--weight-medium)", whiteSpace: "nowrap",
            overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {user?.email}
          </div>
          <div style={{
            fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
            textTransform: "uppercase", letterSpacing: "0.05em",
          }}>
            {ROLE_LABELS[persona] || persona}
          </div>
        </div>
      </div>

      {/* API health */}
      <div style={{
        padding: "var(--space-2) var(--space-4)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "center", gap: "var(--space-2)",
        fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
      }}>
        <StatusDot status={health ? (health.db_ok ? "low" : "high") : "critical"} />
        {health ? `API online · DB ${health.db_ok ? "ok" : "error"}` : "API offline"}
      </div>

      {/* Nav items */}
      <div style={{ flex: 1, padding: "var(--space-2) 0" }}>
        {tabs.map((tabId) => {
          const { label, icon: Icon } = TAB_REGISTRY[tabId];
          const isActive = activePage === tabId;
          return (
            <button
              key={tabId}
              onClick={() => onNavigate(tabId)}
              aria-current={isActive ? "page" : undefined}
              className="nav-item"
              style={{
                display: "flex", alignItems: "center", gap: "var(--space-3)",
                width: "100%", padding: "var(--space-3) var(--space-4)",
                background: isActive ? "var(--color-bg-overlay)" : "transparent",
                borderLeft: `3px solid ${isActive ? "var(--color-info)" : "transparent"}`,
                border: "none",
                color: isActive ? "var(--color-text-primary)" : "var(--color-text-muted)",
                fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
                cursor: "pointer", textAlign: "left",
                transition: "background var(--transition-fast), color var(--transition-fast)",
                outline: "none",
              }}
              onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "var(--color-bg-elevated)"; }}
              onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
              onFocus={(e) => { e.currentTarget.style.boxShadow = "var(--focus-ring)"; }}
              onBlur={(e) => { e.currentTarget.style.boxShadow = "none"; }}
            >
              <Icon size={16} style={{ flexShrink: 0, color: isActive ? "var(--color-info)" : "inherit" }} />
              <span style={{ flex: 1 }}>{label}</span>
              {isActive && <ChevronRight size={12} style={{ color: "var(--color-info)", opacity: 0.7 }} />}
            </button>
          );
        })}
      </div>

      {/* Sign out */}
      <div style={{
        padding: "var(--space-3) var(--space-4)",
        borderTop: "1px solid var(--color-border-subtle)",
      }}>
        <button
          onClick={onSignOut}
          style={{
            display: "flex", alignItems: "center", gap: "var(--space-3)",
            width: "100%", padding: "var(--space-2) var(--space-3)",
            background: "none", border: "none",
            color: "var(--color-text-muted)", fontSize: "var(--text-sm)",
            cursor: "pointer", borderRadius: "var(--radius-md)",
            fontFamily: "var(--font-body)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-bg-elevated)"; e.currentTarget.style.color = "var(--color-text-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "var(--color-text-muted)"; }}
        >
          <LogOut size={16} />
          Sign out
        </button>
        <div style={{
          fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
          textAlign: "center", marginTop: "var(--space-2)", opacity: 0.5,
        }}>
          SARO v8.0.0
        </div>
      </div>
    </nav>
  );
}
