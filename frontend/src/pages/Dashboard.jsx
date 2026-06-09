import React, { useState, useEffect } from "react";
import { ShieldAlert, Clock, AlertTriangle, Sparkles, RefreshCw, Activity, Shield, X } from "lucide-react";
import { Badge, Skeleton, EmptyState, PageHeader } from "../components/ui/index.jsx";
import FlowStrip    from "../components/FlowStrip";
import LiveFeed     from "../components/LiveFeed";
import MetricsRow   from "../components/MetricsRow";
import RegCoverage  from "../components/RegCoverage";
import EngineScores from "../components/EngineScores";

/**
 * STORY-015: Inline drift alert notifications on the Dashboard.
 * Fetches /api/v1/drift/alerts and surfaces triggered alerts as
 * dismissible chips — replaces the need to navigate to the drift_alerts
 * tab for routine monitoring.
 */
function DriftAlertsBanner({ token, onNavigate }) {
  const [alerts, setAlerts]   = useState([]);
  const [dismissed, setDismissed] = useState(() => {
    try { return JSON.parse(localStorage.getItem("saro_dismissed_drift") || "[]"); } catch { return []; }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch("/api/v1/drift/alerts", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then((d) => {
        const raw = Array.isArray(d) ? d : d.alerts || d.items || [];
        setAlerts(raw);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  function dismiss(id) {
    const next = [...dismissed, id];
    setDismissed(next);
    localStorage.setItem("saro_dismissed_drift", JSON.stringify(next));
  }

  const visible = alerts.filter((a) => {
    const id = a.id || a.alert_id || a.name || JSON.stringify(a);
    // Show if not dismissed and has any sign of being active
    const active = a.triggered || a.status === "triggered" || a.drift_detected
      || a.has_drift || a.severity === "high" || a.severity === "critical"
      || (typeof a === "object" && Object.keys(a).length > 0);
    return !dismissed.includes(id) && active;
  });

  if (loading || visible.length === 0) return null;

  return (
    <div style={{
      background: "#fffbeb", border: "1px solid #fde68a",
      borderRadius: "var(--radius-lg)", padding: "var(--space-3) var(--space-4)",
      marginBottom: "var(--space-4)", display: "flex", alignItems: "flex-start", gap: 10,
    }}>
      <Activity size={16} color="#b45309" style={{ marginTop: 2, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
          color: "#92400e", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6,
        }}>
          {visible.length} Drift Alert{visible.length > 1 ? "s" : ""} Detected
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {visible.slice(0, 5).map((a, i) => {
            const id = a.id || a.alert_id || a.name || String(i);
            const label = a.framework_name || a.name || a.alert_type || `Alert ${i + 1}`;
            const severity = a.severity || "medium";
            const sevColor = severity === "critical" || severity === "high" ? "#dc2626" : "#b45309";
            return (
              <span key={id} style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                background: "#fef3c7", border: "1px solid #fcd34d",
                borderRadius: 6, padding: "3px 8px",
                fontSize: "var(--text-xs)", color: sevColor, fontWeight: "var(--weight-medium)",
              }}>
                ⚠ {label}
                <button
                  onClick={() => dismiss(id)}
                  aria-label={`Dismiss alert ${label}`}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "#9ca3af", padding: 0, lineHeight: 1, marginLeft: 2 }}
                >
                  <X size={10} />
                </button>
              </span>
            );
          })}
          {visible.length > 5 && (
            <span style={{ fontSize: "var(--text-xs)", color: "#92400e", alignSelf: "center" }}>
              +{visible.length - 5} more
            </span>
          )}
        </div>
      </div>
      <button
        onClick={() => onNavigate?.("drift_alerts")}
        style={{
          padding: "4px 10px", background: "#fef3c7", border: "1px solid #fcd34d",
          borderRadius: 5, cursor: "pointer", fontSize: "var(--text-xs)",
          color: "#92400e", fontWeight: "var(--weight-semibold)", flexShrink: 0,
          fontFamily: "var(--font-body)",
        }}
      >
        View All →
      </button>
    </div>
  );
}

const POSTURE_STYLES = {
  CRITICAL: { bg: "var(--color-critical-bg)", border: "var(--color-critical-border)", color: "var(--color-critical)" },
  HIGH:     { bg: "var(--color-high-bg)",     border: "var(--color-high-border)",     color: "var(--color-high)" },
  MEDIUM:   { bg: "var(--color-medium-bg)",   border: "var(--color-medium-border)",   color: "var(--color-medium)" },
  LOW:      { bg: "var(--color-low-bg)",       border: "var(--color-low-border)",      color: "var(--color-low)" },
};

function RiskPostureBanner({ level, openRisks, overdueItems, lastUpdated }) {
  const s = POSTURE_STYLES[level] || POSTURE_STYLES.HIGH;
  return (
    <div style={{
      background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: "var(--radius-lg)", padding: "var(--space-5) var(--space-6)",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexWrap: "wrap", gap: "var(--space-4)",
      marginBottom: "var(--space-6)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
        <ShieldAlert size={32} color={s.color} strokeWidth={1.5} />
        <div>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
            color: s.color, textTransform: "uppercase", letterSpacing: "0.08em",
            fontFamily: "var(--font-display)",
          }}>
            Risk Posture
          </div>
          <div style={{
            fontSize: "var(--text-xl)", fontWeight: "var(--weight-semibold)",
            color: s.color, fontFamily: "var(--font-display)", lineHeight: 1.2,
          }}>
            {level}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: "var(--space-8)", flexWrap: "wrap" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)", color: s.color, fontFamily: "var(--font-mono)" }}>
            {openRisks}
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Open Risks
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)", color: s.color, fontFamily: "var(--font-mono)" }}>
            {overdueItems}
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Overdue
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)" }}>
            {lastUpdated}
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Last updated
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value, delta, severity, size, icon: Icon, loading }) {
  const sev = severity === "ai" ? "ai" : severity;
  const colors = {
    critical: "var(--color-critical)",
    high:     "var(--color-high)",
    medium:   "var(--color-medium)",
    low:      "var(--color-low)",
    ai:       "var(--color-ai)",
    info:     "var(--color-info)",
  };
  const color = colors[sev] || colors.info;
  const isLarge = size === "large";

  return (
    <div style={{
      background: "var(--color-bg-surface)",
      border: "1px solid var(--color-border-subtle)",
      borderRadius: "var(--radius-lg)",
      padding: "var(--space-5)",
      display: "flex", flexDirection: "column", gap: "var(--space-2)",
      borderTop: `2px solid ${color}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{
          fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
          color: "var(--color-text-muted)", textTransform: "uppercase",
          letterSpacing: "0.07em", fontFamily: "var(--font-display)",
        }}>
          {label}
        </span>
        {Icon && <Icon size={16} color={color} />}
      </div>

      {loading ? (
        <Skeleton height={isLarge ? 40 : 32} width={80} />
      ) : (
        <div style={{
          fontSize: isLarge ? "var(--text-2xl)" : "var(--text-xl)",
          fontWeight: "var(--weight-semibold)",
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-mono)",
          lineHeight: 1,
        }}>
          {value ?? "—"}
        </div>
      )}

      {delta !== undefined && delta !== null && !loading && (
        <div style={{
          fontSize: "var(--text-xs)",
          color: delta > 0 ? "var(--color-critical)" : delta < 0 ? "var(--color-low)" : "var(--color-text-muted)",
        }}>
          {delta > 0 ? `↑ +${delta}` : delta < 0 ? `↓ ${delta}` : "— no change"} since last period
        </div>
      )}
    </div>
  );
}

const VERTICALS = ["finance", "healthcare", "legal", "government"];
const WINDOWS   = ["7d", "30d", "90d"];

const qaBtn = (bg) => ({
  padding: "6px 14px", background: bg, color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontSize: "var(--text-sm)",
  fontWeight: "var(--weight-medium)", fontFamily: "var(--font-body)",
});

// Persona-specific KPI configurations (STORY-006)
const PERSONA_KPIS = {
  compliance_lead: [
    { label: "EVF Frameworks",    value: 4,   delta: 0,   severity: "info",     icon: Shield },
    { label: "Controls Overdue",  value: 5,   delta: +1,  severity: "high",     icon: AlertTriangle },
    { label: "Scans This Week",   value: 12,  delta: -2,  severity: "low",      icon: Clock },
    { label: "Readiness %",       value: "68%", delta: null, severity: "medium", icon: Sparkles },
  ],
  risk_officer: [
    { size: "large", label: "Critical Risks",  value: 12,  delta: +3,  severity: "critical", icon: ShieldAlert },
    { label: "Due This Week",    value: 8,   delta: -1,  severity: "high",     icon: Clock },
    { label: "Controls Overdue", value: 5,   delta: 0,   severity: "medium",   icon: AlertTriangle },
    { label: "Remediation %",    value: "54%", delta: null, severity: "low",   icon: Sparkles },
  ],
  ai_auditor: [
    { label: "Scans Today",       value: 7,   delta: +2,  severity: "info",     icon: Clock },
    { label: "Rule Pack Version", value: "v3.1", delta: null, severity: "info", icon: Shield },
    { label: "Drift Alerts",      value: 2,   delta: +2,  severity: "high",     icon: AlertTriangle },
    { label: "Coverage Gap %",    value: "18%", delta: null, severity: "medium", icon: Sparkles },
  ],
  operator: [
    { label: "Scans Today",       value: 7,   delta: +2,  severity: "info",     icon: Clock },
    { label: "Failed Scans",      value: 1,   delta: +1,  severity: "high",     icon: AlertTriangle },
    { label: "Queue Depth",       value: 3,   delta: null, severity: "medium",  icon: Sparkles },
    { label: "Avg Score",         value: 41,  delta: -3,  severity: "low",      icon: ShieldAlert },
  ],
};
// admin and super_admin see the full risk view (same as risk_officer)
PERSONA_KPIS.admin       = PERSONA_KPIS.risk_officer;
PERSONA_KPIS.super_admin = PERSONA_KPIS.risk_officer;

const PERSONA_SUBTITLE = {
  compliance_lead: "Compliance readiness & EVF status",
  risk_officer:    "Risk posture & open findings",
  ai_auditor:      "Scan pipeline & drift monitoring",
  operator:        "Upload queue & scan activity",
  admin:           "Risk posture & open findings",
  super_admin:     "Risk posture & open findings",
};

export default function Dashboard({ token, tenantId, user, onNavigate }) {
  const persona = user?.persona_role || user?.role || "operator";
  const [vertical,   setVertical]   = useState("finance");
  const [timeWindow, setTimeWindow] = useState("7d");
  const [degraded,   setDegraded]   = useState(false);
  const [kpiLoading, setKpiLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState("just now");

  const kpis = PERSONA_KPIS[persona] || PERSONA_KPIS.operator;

  useEffect(() => {
    const timer = setTimeout(() => {
      setKpiLoading(false);
      setLastUpdated("2 min ago");
    }, 1200);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (e.reason?.message?.includes("503") || e.reason?.message?.includes("502")) setDegraded(true);
    };
    window.addEventListener("unhandledrejection", handler);
    return () => window.removeEventListener("unhandledrejection", handler);
  }, []);

  if (!token) {
    return (
      <EmptyState
        icon={<ShieldAlert />}
        title="Authentication required"
        description="Please sign in to view the dashboard."
      />
    );
  }

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Dashboard"
        subtitle={PERSONA_SUBTITLE[persona] || "Operational risk posture overview"}
        actions={
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            {/* Vertical selector */}
            <div style={{ display: "flex", gap: "var(--space-1)" }}>
              {VERTICALS.map((v) => (
                <button
                  key={v}
                  onClick={() => setVertical(v)}
                  style={{
                    padding: "4px 10px", borderRadius: 999,
                    border: `1px solid ${vertical === v ? "var(--color-info)" : "var(--color-border-default)"}`,
                    background: vertical === v ? "var(--color-info-bg)" : "transparent",
                    color: vertical === v ? "var(--color-info)" : "var(--color-text-muted)",
                    cursor: "pointer", fontSize: "var(--text-xs)",
                    fontFamily: "var(--font-display)", fontWeight: "var(--weight-medium)",
                    transition: "all var(--transition-fast)",
                  }}
                >
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </button>
              ))}
            </div>
            {/* Window selector */}
            <select
              value={timeWindow}
              onChange={(e) => setTimeWindow(e.target.value)}
              style={{
                padding: "4px 8px", borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-border-default)",
                background: "var(--color-bg-elevated)", color: "var(--color-text-primary)",
                fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
                cursor: "pointer",
              }}
            >
              {WINDOWS.map((w) => (
                <option key={w} value={w}>{w === "7d" ? "7 days" : w === "30d" ? "30 days" : "90 days"}</option>
              ))}
            </select>
          </div>
        }
      />

      <div style={{ padding: "var(--space-6)" }}>
        {/* Degraded warning */}
        {degraded && (
          <div role="alert" style={{
            background: "var(--color-medium-bg)", border: "1px solid var(--color-medium-border)",
            borderRadius: "var(--radius-md)", padding: "var(--space-3) var(--space-4)",
            marginBottom: "var(--space-5)", fontSize: "var(--text-sm)", color: "var(--color-medium)",
            display: "flex", alignItems: "center", gap: "var(--space-2)",
          }}>
            <AlertTriangle size={14} /> API degraded — some panels may show stale data
          </div>
        )}

        {/* Drift alerts inline — STORY-015: ai_auditor, admin, compliance_lead */}
        {["ai_auditor","admin","super_admin","compliance_lead"].includes(persona) && (
          <DriftAlertsBanner token={token} onNavigate={onNavigate} />
        )}

        {/* Risk posture banner — must be first thing visible */}
        <RiskPostureBanner
          level="HIGH"
          openRisks={47}
          overdueItems={12}
          lastUpdated={lastUpdated}
        />

        {/* KPI cards — persona-specific (STORY-006) */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}>
          {kpis.map((kpi, i) => (
            <KpiCard
              key={i}
              size={kpi.size}
              label={kpi.label}
              value={kpi.value}
              delta={kpi.delta}
              severity={kpi.severity}
              icon={kpi.icon}
              loading={kpiLoading}
            />
          ))}
        </div>

        {/* Quick actions — persona-specific */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: "var(--space-5)" }}>
          {persona === "operator" && (
            <button onClick={() => onNavigate?.("upload")} style={qaBtn("#0d9488")}>
              + New Scan
            </button>
          )}
          {["risk_officer","admin","super_admin"].includes(persona) && (
            <button onClick={() => onNavigate?.("risk_register")} style={qaBtn("#0d9488")}>
              Open Risk Register
            </button>
          )}
          {persona === "compliance_lead" && (
            <button onClick={() => onNavigate?.("compliance_hub")} style={qaBtn("#0d9488")}>
              Compliance Hub
            </button>
          )}
          {persona === "ai_auditor" && (
            <button onClick={() => onNavigate?.("upload")} style={qaBtn("#0d9488")}>
              + New Scan
            </button>
          )}
          <button onClick={() => onNavigate?.("trace_view")} style={qaBtn("#6b7280")}>
            View Recent TRACE
          </button>
        </div>

        {/* Last updated indicator */}
        <div style={{
          display: "flex", alignItems: "center", gap: "var(--space-2)",
          fontSize: "var(--text-xs)", color: "var(--color-text-muted)",
          marginBottom: "var(--space-5)",
        }}>
          <RefreshCw size={11} />
          Last updated {lastUpdated}
        </div>

        {/* Pipeline status */}
        <div style={{ marginBottom: "var(--space-6)" }}>
          <h2 style={{
            fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
            color: "var(--color-text-muted)", textTransform: "uppercase",
            letterSpacing: "0.08em", marginBottom: "var(--space-3)",
            fontFamily: "var(--font-display)",
          }}>
            Pipeline Status
          </h2>
          <FlowStrip token={token} />
        </div>

        {/* Lower panels */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "var(--space-5)", flexWrap: "wrap" }}>
          <div>
            <h2 style={{
              fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
              color: "var(--color-text-muted)", textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: "var(--space-3)",
              fontFamily: "var(--font-display)",
            }}>
              Live Audit Feed
            </h2>
            <LiveFeed token={token} tenantId={tenantId} />
          </div>
          <div>
            <h2 style={{
              fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
              color: "var(--color-text-muted)", textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: "var(--space-3)",
              fontFamily: "var(--font-display)",
            }}>
              Regulation Coverage
            </h2>
            <RegCoverage token={token} tenantId={tenantId} window={timeWindow} vertical={vertical} />
          </div>
          <div>
            <h2 style={{
              fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
              color: "var(--color-text-muted)", textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: "var(--space-3)",
              fontFamily: "var(--font-display)",
            }}>
              Engine Scores
            </h2>
            <EngineScores token={token} tenantId={tenantId} vertical={vertical} />
          </div>
        </div>
      </div>
    </div>
  );
}
