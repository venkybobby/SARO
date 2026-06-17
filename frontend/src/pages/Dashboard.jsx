import React, { useState, useEffect } from "react";
import { ShieldAlert, Clock, AlertTriangle, Sparkles, RefreshCw, Activity, Shield, X, ChevronDown, ChevronRight, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Badge, Skeleton, EmptyState, PageHeader } from "../components/ui/index.jsx";
import FlowStrip    from "../components/FlowStrip";
import LiveFeed     from "../components/LiveFeed";
import MetricsRow   from "../components/MetricsRow";
import RegCoverage  from "../components/RegCoverage";
import EngineScores from "../components/EngineScores";

const POSTURE_STYLES = {
  CRITICAL: { bg: "var(--color-critical-bg)", border: "var(--color-critical-border)", color: "var(--color-critical)" },
  HIGH:     { bg: "var(--color-high-bg)",     border: "var(--color-high-border)",     color: "var(--color-high)" },
  MEDIUM:   { bg: "var(--color-medium-bg)",   border: "var(--color-medium-border)",   color: "var(--color-medium)" },
  LOW:      { bg: "var(--color-low-bg)",       border: "var(--color-low-border)",      color: "var(--color-low)" },
};

/** One numeric stat in the posture banner. Clickable when onClick is supplied. */
function BannerStat({ value, label, color, loading, onClick }) {
  const clickable = typeof onClick === "function";
  return (
    <div
      onClick={onClick}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
      style={{ textAlign: "center", cursor: clickable ? "pointer" : "default" }}
      title={clickable ? `View ${label}` : undefined}
    >
      {loading ? <Skeleton height={32} width={40} /> : (
        <div style={{
          fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)",
          color, fontFamily: "var(--font-mono)",
          textDecoration: clickable ? "underline" : "none", textUnderlineOffset: 3,
        }}>
          {value}
        </div>
      )}
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </div>
    </div>
  );
}

function RiskPostureBanner({ level, riskScore, openRisks, lastUpdated, loading, onOpenRisks }) {
  const s = POSTURE_STYLES[level] || POSTURE_STYLES.HIGH;
  return (
    <div style={{
      background: s.bg, border: `1px solid ${s.border}`,
      borderRadius: "var(--radius-lg)", padding: "var(--space-5) var(--space-6)",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      flexWrap: "wrap", gap: "var(--space-4)",
      marginBottom: "var(--space-4)",
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
          {loading ? (
            <Skeleton height={28} width={80} />
          ) : (
            <div style={{
              fontSize: "var(--text-xl)", fontWeight: "var(--weight-semibold)",
              color: s.color, fontFamily: "var(--font-display)", lineHeight: 1.2,
            }}>
              {level}
            </div>
          )}
        </div>
      </div>
      <div style={{ display: "flex", gap: "var(--space-8)", flexWrap: "wrap" }}>
        {/* overall_risk_score — the cleanest single posture number */}
        <BannerStat value={riskScore} label="Risk Score" color={s.color} loading={loading} />
        {/* real open-findings count (drill-through), not the prior audit_count mislabel */}
        <BannerStat value={openRisks} label="Open Risks" color={s.color} loading={loading} onClick={onOpenRisks} />
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

function KpiCard({ label, value, severity, size, icon: Icon, loading, sub, onClick }) {
  const colors = {
    critical: "var(--color-critical)",
    high:     "var(--color-high)",
    medium:   "var(--color-medium)",
    low:      "var(--color-low)",
    ai:       "var(--color-ai)",
    info:     "var(--color-info)",
  };
  const color    = colors[severity] || colors.info;
  const isLarge  = size === "large";
  const clickable = typeof onClick === "function";

  return (
    <div
      onClick={onClick}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
      title={clickable ? `View ${label}` : undefined}
      style={{
        background: "var(--color-bg-surface)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-lg)",
        padding: "var(--space-5)",
        display: "flex", flexDirection: "column", gap: "var(--space-2)",
        borderTop: `2px solid ${color}`,
        cursor: clickable ? "pointer" : "default",
      }}
    >
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

      {sub && !loading && (
        <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
          {sub}
        </div>
      )}
    </div>
  );
}

/**
 * Real 7-day trend line backed by /api/v1/risk/whats-changed.
 * Replaces the previously fabricated per-card trend arrows — a measured-change
 * claim must be backed by data in a compliance product.
 */
function TrendLine({ data }) {
  if (!data || (data.current_avg_score == null && data.score_delta == null)) return null;
  const dir   = data.delta_direction || "flat";
  const delta = Math.abs(data.score_delta ?? 0);
  const Icon  = dir === "up" ? TrendingUp : dir === "down" ? TrendingDown : Minus;
  // Higher risk score is worse: up = critical (red), down = improvement (green).
  const color = dir === "up" ? "var(--color-critical)" : dir === "down" ? "var(--color-low)" : "var(--color-text-muted)";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: "var(--space-2)",
      marginBottom: "var(--space-6)", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)",
    }}>
      <Icon size={15} color={color} />
      <span>
        7-day avg risk score <strong style={{ fontFamily: "var(--font-mono)" }}>{data.current_avg_score}</strong>
        {dir !== "flat" && (
          <> — <span style={{ color }}>{dir === "up" ? "↑" : "↓"} {delta}</span> vs prior 7 days</>
        )}
        {dir === "flat" && <> — no change vs prior 7 days</>}
        {data.new_audits_count != null && <> · {data.new_audits_count} new audit{data.new_audits_count === 1 ? "" : "s"}</>}
      </span>
    </div>
  );
}

/**
 * STORY-015: Inline drift alert notifications.
 * Fetches /api/v1/rules/drift-alerts (shared with DriftAlerts page).
 * Renders triggered alerts as dismissible amber chips.
 */
function DriftAlertsBanner({ token, onNavigate }) {
  const [alerts, setAlerts]   = useState([]);
  const [dismissed, setDismissed] = useState(() => {
    try { return JSON.parse(localStorage.getItem("saro_dismissed_drift") || "[]"); } catch { return []; }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch("/api/v1/rules/drift-alerts", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        const raw = Array.isArray(d) ? d : (d?.alerts || []);
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
    const active = a.triggered || a.status === "triggered"
      || a.drift_detected || a.has_drift
      || a.severity === "high" || a.severity === "critical";
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
            const id    = a.id || a.alert_id || a.name || String(i);
            const label = a.framework_name || a.name || a.alert_type || `Alert ${i + 1}`;
            const sev   = a.severity || "medium";
            const sevColor = sev === "critical" || sev === "high" ? "#dc2626" : "#b45309";
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
                  aria-label={`Dismiss ${label}`}
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

const VERTICALS = ["finance", "healthcare", "legal", "government"];
const WINDOWS   = ["7d", "30d", "90d"];

const qaBtn = (bg) => ({
  padding: "6px 14px", background: bg, color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontSize: "var(--text-sm)",
  fontWeight: "var(--weight-medium)", fontFamily: "var(--font-body)",
});

// Persona-specific KPI configurations (STORY-006).
// Deltas removed (FND-023): a fabricated per-card trend arrow must be backed by
// data — the real 7-day trend is shown once in <TrendLine/>. Values marked
// `placeholder: true` are template defaults with no backing endpoint yet; the
// live values below are overridden from /risk/summary in deriveKpis().
const PERSONA_KPIS = {
  compliance_lead: [
    { label: "EVF Frameworks",    value: 4,   severity: "info",     icon: Shield },
    { label: "Controls Overdue",  value: 5,   severity: "high",     icon: AlertTriangle, placeholder: true },
    { label: "Scans This Week",   value: 12,  severity: "low",      icon: Clock },
    { label: "Readiness %",       value: "68%", severity: "medium", icon: Sparkles, placeholder: true },
  ],
  risk_officer: [
    { size: "large", label: "Critical Risks",  value: 12,  severity: "critical", icon: ShieldAlert },
    { label: "Due This Week",    value: 8,   severity: "high",     icon: Clock, placeholder: true },
    { label: "Controls Overdue", value: 5,   severity: "medium",   icon: AlertTriangle, placeholder: true },
    { label: "Remediation %",    value: "54%", severity: "low",    icon: Sparkles },
  ],
  ai_auditor: [
    { label: "Scans Today",       value: 7,   severity: "info",     icon: Clock },
    { label: "Rule Pack Version", value: "v3.1", severity: "info",  icon: Shield, placeholder: true },
    { label: "Drift Alerts",      value: 2,   severity: "high",     icon: AlertTriangle, placeholder: true },
    { label: "Coverage Gap %",    value: "18%", severity: "medium", icon: Sparkles, placeholder: true },
  ],
  operator: [
    { label: "Scans Today",       value: 7,   severity: "info",     icon: Clock },
    { label: "Failed Scans",      value: 1,   severity: "high",     icon: AlertTriangle, placeholder: true },
    { label: "Queue Depth",       value: 3,   severity: "medium",   icon: Sparkles, placeholder: true },
    { label: "Avg Score",         value: 41,  severity: "low",      icon: ShieldAlert },
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

// Where a KPI card / banner number drills through to, per persona.
const PERSONA_DRILL = {
  compliance_lead: "compliance_hub",
  risk_officer:    "risk_register",
  admin:           "risk_register",
  super_admin:     "risk_register",
  ai_auditor:      "trace_view",
  operator:        "upload",
};

const RAG_TO_POSTURE = { GREEN: "LOW", AMBER: "MEDIUM", RED: "CRITICAL" };

/** Fetches /api/v1/risk/summary — backs the posture banner and KPI cards. */
function useDashboardData(token, onError) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    fetch("/api/v1/risk/summary", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!r.ok) { onError?.(r.status); return null; }
        return r.json();
      })
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { onError?.(0); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, reloadKey]);

  return { data, loading, refetch: () => setReloadKey((k) => k + 1) };
}

/** Fetches /api/v1/risk/whats-changed — real 7-day delta for <TrendLine/>. */
function useWhatsChanged(token) {
  const [delta, setDelta] = useState(null);
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetch("/api/v1/risk/whats-changed", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (!cancelled && d) setDelta(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [token]);
  return delta;
}

/** Maps the live risk summary onto the persona's KPI card template. */
function deriveKpis(data, persona) {
  const base = (PERSONA_KPIS[persona] || PERSONA_KPIS.operator).map((kpi) => ({ ...kpi }));
  const criticalCount = data.critical_findings_count;
  const remediationPct = data.remediation_pct;
  const auditCount = data.audit_count;

  if (persona === "risk_officer" || persona === "admin" || persona === "super_admin") {
    // base[0] is "Critical Risks" — bind to the critical count so value matches label.
    if (criticalCount != null) { base[0].value = criticalCount; base[0].placeholder = false; }
    if (remediationPct != null) { base[3].value = `${remediationPct}%`; base[3].placeholder = false; }
  } else if (persona === "compliance_lead") {
    if (auditCount != null) { base[2].value = auditCount; base[2].placeholder = false; }
  } else {
    if (auditCount != null) { base[0].value = auditCount; base[0].placeholder = false; }
  }
  return base;
}

/** Maps the live risk summary onto the risk posture banner's props. */
function derivePosture(data) {
  return {
    postureLevel: RAG_TO_POSTURE[data.rag_status] || "HIGH",
    riskScore: data.overall_risk_score ?? "—",
    openRisks: data.open_findings_count ?? (data.top_findings?.length ?? "—"),
    lastUpdated: data.generated_at ? new Date(data.generated_at).toLocaleString() : "—",
  };
}

const selectStyle = {
  padding: "3px 6px", borderRadius: "var(--radius-md)",
  border: "1px solid var(--color-border-default)",
  background: "var(--color-bg-elevated)", color: "var(--color-text-primary)",
  fontSize: "var(--text-xs)", fontFamily: "var(--font-body)",
  cursor: "pointer",
};

function VerticalSelector({ vertical, onChange }) {
  return (
    <select value={vertical} onChange={(e) => onChange(e.target.value)} aria-label="Vertical" style={selectStyle}>
      {VERTICALS.map((v) => (
        <option key={v} value={v}>{v.charAt(0).toUpperCase() + v.slice(1)}</option>
      ))}
    </select>
  );
}

function WindowSelector({ window: win, onChange }) {
  return (
    <select value={win} onChange={(e) => onChange(e.target.value)} aria-label="Time window" style={selectStyle}>
      {WINDOWS.map((w) => (
        <option key={w} value={w}>{w === "7d" ? "7 days" : w === "30d" ? "30 days" : "90 days"}</option>
      ))}
    </select>
  );
}

export default function Dashboard({ token, tenantId, user, onNavigate }) {
  const persona = user?.persona_role || user?.role || "operator";
  const [vertical,   setVertical]   = useState("finance");
  const [timeWindow, setTimeWindow] = useState("7d");
  const [degraded,   setDegraded]   = useState(false);
  const [showOperationalDetail, setShowOperationalDetail] = useState(false);

  const { data, loading, refetch } = useDashboardData(token, () => setDegraded(true));
  const whatsChanged = useWhatsChanged(token);

  const kpis    = data ? deriveKpis(data, persona)    : [];
  const posture = data ? derivePosture(data)           : { postureLevel: "HIGH", riskScore: "—", openRisks: "—", lastUpdated: "—" };
  const drill   = PERSONA_DRILL[persona] || "risk_register";
  const isEmpty = data && (data.audit_count === 0);

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
          <button
            onClick={refetch}
            disabled={loading}
            aria-label="Refresh dashboard"
            style={{
              padding: "4px 8px", borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border-default)",
              background: "var(--color-bg-elevated)", cursor: loading ? "default" : "pointer",
              color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 4,
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
          </button>
        }
      />

      <div style={{ padding: "var(--space-6)" }}>
        {/* Degraded warning — wired to the actual fetch error path */}
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

        {isEmpty ? (
          <EmptyState
            icon={<ShieldAlert />}
            title="No audits yet"
            description="Run your first scan to populate your risk posture, findings, and trend."
            action={
              <button onClick={() => onNavigate?.("upload")} style={qaBtn("#0d9488")}>
                + New Scan
              </button>
            }
          />
        ) : (
          <>
            {/* Risk posture banner — must be first thing visible */}
            <RiskPostureBanner
              level={posture.postureLevel}
              riskScore={posture.riskScore}
              openRisks={posture.openRisks}
              lastUpdated={posture.lastUpdated}
              loading={loading}
              onOpenRisks={() => onNavigate?.(drill)}
            />

            {/* Real 7-day trend (replaces fabricated per-card deltas) */}
            <TrendLine data={whatsChanged} />

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
                  severity={kpi.severity}
                  icon={kpi.icon}
                  loading={loading}
                  sub={kpi.placeholder ? "sample — not yet wired to live data" : undefined}
                  onClick={() => onNavigate?.(drill)}
                />
              ))}
            </div>

            {/* Quick actions — persona-specific (single block; the duplicate was removed, FND-021) */}
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
          </>
        )}

        {/* Operational detail — collapsed by default for risk_officer/compliance_lead,
            who care more about posture/KPIs than pipeline internals */}
        <div style={{ marginBottom: "var(--space-6)" }}>
          <button
            onClick={() => setShowOperationalDetail((v) => !v)}
            aria-expanded={showOperationalDetail}
            style={{
              display: "flex", alignItems: "center", gap: "var(--space-2)",
              background: "none", border: "none", cursor: "pointer", padding: 0,
              fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
              color: "var(--color-text-muted)", textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: "var(--space-3)",
              fontFamily: "var(--font-display)",
            }}
          >
            {showOperationalDetail ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Operational Detail
          </button>

          {showOperationalDetail && (
            <>
              {/* Single shared control row for the operational panels — one vertical +
                  one window selector that actually drive RegCoverage/EngineScores
                  (previously two synced dropdowns + a decorative header window picker) */}
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Filters
                </span>
                <VerticalSelector vertical={vertical} onChange={setVertical} />
                <WindowSelector window={timeWindow} onChange={setTimeWindow} />
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

              {/* Lower panels — responsive auto-fit grid (grid ignores flexWrap) */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "var(--space-5)" }}>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
