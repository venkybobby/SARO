import React, { useEffect, useRef, useState } from "react";
import {
  LayoutDashboard, Shield, Search, Package,
  Map, Wrench, Activity, Building2, Upload, Settings,
  ClipboardList, BookOpen, Users, Lightbulb, FileText,
  AlertTriangle, Lock, ShieldCheck, LogOut, ChevronRight,
  ShieldAlert, Sparkles, LineChart, ChevronDown,
} from "lucide-react";
import { StatusDot } from "./ui/index.jsx";

const PERSONA_TABS = {
  compliance_lead: [
    "dashboard","compliance_hub","trace_view",
    "trust_center",
    "aims","onboarding","upload","evaluations","reports",
  ],
  risk_officer: ["dashboard","risk_register","trace_view","ai_insights","reports"],
  ai_auditor: [
    "dashboard","trace_view",
    "rule_packs","coverage_gap","remediation","drift_alerts","upload",
    "knowledge_portal",
  ],
  admin: [
    "dashboard","compliance_hub","trace_view",
    "trust_center",
    "rule_packs","coverage_gap","remediation",
    "drift_alerts","aims","onboarding","upload",
    "admin_settings","evaluations","evf_admin","demo_requests",
    "risk_register","ai_insights","reports","settings","knowledge_portal",
  ],
  super_admin: [
    "dashboard","compliance_hub","trace_view",
    "trust_center",
    "rule_packs","coverage_gap","remediation",
    "drift_alerts","aims","onboarding","upload",
    "admin_settings","evaluations","risk_register","ai_insights","reports","settings",
  ],
  operator: ["dashboard","upload","trace_view","remediation","knowledge_portal"],
};

const TAB_REGISTRY = {
  dashboard:        { label: "Dashboard",         icon: LayoutDashboard, page: "dashboard" },
  compliance_hub:   { label: "Compliance Hub",    icon: Shield,          page: "compliance_hub" },
  trace_view:       { label: "TRACE View",         icon: Search,          page: "trace_view" },
  evidence_export:  { label: "Evidence Export",    icon: Package,         page: "trace_view" },
  // STORY-113: Risk Summary (and its Vendor Risk alias) merged into Risk Register.
  trust_center:     { label: "Trust Center",       icon: ShieldCheck,     page: "trust_center" },
  rule_packs:       { label: "Rule Packs",         icon: Package,         page: "rule_packs" },
  coverage_gap:     { label: "Coverage Gap",       icon: Map,             page: "coverage_gap" },
  remediation:      { label: "Remediation",        icon: Wrench,          page: "remediation" },
  drift_alerts:     { label: "Drift Alerts",       icon: Activity,        page: "drift_alerts" },
  onboarding:       { label: "Onboarding",         icon: Building2,       page: "onboarding" },
  upload:           { label: "Upload & Scan",      icon: Upload,          page: "upload" },
  admin_settings:   { label: "Admin Settings",     icon: Settings,        page: "admin_settings" },
  aims:             { label: "AIMS",               icon: ClipboardList,   page: "aims" },
  evaluations:      { label: "Evaluations",        icon: BookOpen,        page: "evaluations" },
  evf_admin:        { label: "EVF Status",         icon: Lock,            page: "evf_admin" },
  demo_requests:    { label: "Demo Requests",      icon: Users,           page: "demo_requests" },
  risk_register:    { label: "Risk Register",      icon: ShieldAlert,     page: "risk_register" },
  ai_insights:      { label: "AI Insights",        icon: Sparkles,        page: "ai_insights" },
  reports:          { label: "Reports",            icon: LineChart,       page: "reports" },
  settings:         { label: "Settings",           icon: Settings,        page: "settings" },
  knowledge_portal: { label: "Knowledge Portal",   icon: BookOpen,        page: "knowledge_portal" },
};

const ROLE_LABELS = {
  compliance_lead: "Compliance Lead",
  risk_officer:    "Risk Officer",
  ai_auditor:      "AI Auditor",
  admin:           "Admin",
  super_admin:     "Super Admin",
  operator:        "Operator",
};

const SWITCHABLE_PERSONAS = [
  "compliance_lead","risk_officer","ai_auditor","admin","super_admin","operator",
];

export default function Sidebar({ user, activePage, onNavigate, onSignOut, token, onUserUpdate }) {
  const [health, setHealth] = useState(null);
  const [switchOpen, setSwitchOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const switchRef = useRef(null);

  // canSwitch must check the immutable base role, NOT persona_role.
  // persona_role is the current view; role is the account-level assignment.
  // A super_admin who switched to "risk_officer" still has role="super_admin"
  // and must be able to switch back — including after logout/login.
  const canSwitch = ["admin","super_admin"].includes(user?.role);

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

  useEffect(() => {
    if (!switchOpen) return;
    function handleClick(e) {
      if (switchRef.current && !switchRef.current.contains(e.target)) setSwitchOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [switchOpen]);

  async function switchPersona(newPersona) {
    if (!user?.id) return;
    setSwitching(true);
    try {
      const r = await fetch(`/api/v1/auth/users/${user.id}/persona?persona_role=${newPersona}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      const updated = await r.json();
      onUserUpdate?.({ ...user, persona_role: updated.persona_role });
    } catch {
      // silently ignore — user stays on current persona
    } finally {
      setSwitching(false);
      setSwitchOpen(false);
    }
  }

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
      <div
        ref={switchRef}
        style={{
          padding: "var(--space-3) var(--space-4)",
          borderBottom: "1px solid var(--color-border-subtle)",
          position: "relative",
        }}
      >
        <div
          onClick={() => canSwitch && setSwitchOpen((o) => !o)}
          style={{
            display: "flex", alignItems: "center", gap: "var(--space-3)",
            cursor: canSwitch ? "pointer" : "default",
          }}
        >
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
          <div style={{ overflow: "hidden", flex: 1 }}>
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
          {canSwitch && (
            <ChevronDown size={12} style={{ color: "var(--color-text-muted)", flexShrink: 0 }} />
          )}
        </div>

        {switchOpen && (
          <div style={{
            position: "absolute", left: "var(--space-4)", right: "var(--space-4)",
            top: "calc(100% + 4px)", zIndex: 100,
            background: "var(--color-bg-surface)",
            border: "1px solid var(--color-border-default)",
            borderRadius: "var(--radius-md)",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            overflow: "hidden",
          }}>
            <div style={{
              padding: "var(--space-2) var(--space-3)",
              fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
              fontWeight: "var(--weight-semibold)", textTransform: "uppercase",
              letterSpacing: "0.06em", borderBottom: "1px solid var(--color-border-subtle)",
            }}>
              Switch persona
            </div>
            {SWITCHABLE_PERSONAS.map((p) => (
              <button
                key={p}
                disabled={switching || p === persona}
                onClick={() => switchPersona(p)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  padding: "var(--space-2) var(--space-3)",
                  background: p === persona ? "var(--color-bg-overlay)" : "transparent",
                  border: "none", cursor: p === persona ? "default" : "pointer",
                  fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
                  color: p === persona ? "var(--color-info)" : "var(--color-text-primary)",
                  fontWeight: p === persona ? "var(--weight-semibold)" : "var(--weight-normal)",
                }}
                onMouseEnter={(e) => { if (p !== persona) e.currentTarget.style.background = "var(--color-bg-elevated)"; }}
                onMouseLeave={(e) => { if (p !== persona) e.currentTarget.style.background = "transparent"; }}
              >
                {ROLE_LABELS[p] || p}
                {p === persona && " ✓"}
              </button>
            ))}
          </div>
        )}
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
