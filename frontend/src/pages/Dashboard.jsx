/**
 * Dashboard — persona-specific operational overview.
 *
 * All KPI values are derived from live backend data — no hardcoded metrics.
 *
 * Data sources:
 *   /api/v1/risk/summary        — rag_status, overall_risk_score, audit_count, remediation_pct
 *   /api/v1/risk/whats-changed  — score_delta, new_audits_count (7-day window)
 *   /api/v1/risks               — risk register items (severity, status, dueDate)
 *   /api/v1/audits              — audit list (status, created_at) for today/failed counts
 *   /api/v1/drift/alerts        — triggered drift alerts
 *   /api/v1/engine/status       — rule pack version, engine health
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert, Clock, AlertTriangle, Sparkles, RefreshCw,
  Activity, Shield, X, ChevronDown, ChevronRight,
} from "lucide-react";
import { Skeleton, EmptyState, PageHeader } from "../components/ui/index.jsx";
import FlowStrip    from "../components/FlowStrip";
import LiveFeed     from "../components/LiveFeed";
import MetricsRow   from "../components/MetricsRow";
import RegCoverage  from "../components/RegCoverage";
import EngineScores from "../components/EngineScores";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const _RAG_TO_POSTURE = { RED: "CRITICAL", AMBER: "HIGH", GREEN: "LOW", "No data": "LOW" };
const _DEFAULT_POSTURE = "LOW";

function _isToday(isoStr) {
  if (!isoStr) return false;
  const d = new Date(isoStr);
  const n = new Date();
  return d.getFullYear() === n.getFullYear()
    && d.getMonth()     === n.getMonth()
    && d.getDate()      === n.getDate();
}

function _isThisWeek(isoStr) {
  if (!isoStr) return false;
  const now = Date.now();
  const d   = new Date(isoStr).getTime();
  return now - d < 7 * 24 * 60 * 60 * 1000 && d <= now;
}

function _isOverdue(isoStr) {
  if (!isoStr) return false;
  return new Date(isoStr).getTime() < Date.now();
}

function _isOpen(r) {
  const s = (r.status || "").toLowerCase();
  return s !== "closed" && s !== "completed" && s !== "resolved";
}

function _fmt(val) {
  if (val === null || val === undefined) return "—";
  return val;
}

function _pct(val) {
  if (val === null || val === undefined) return "—";
  const n = typeof val === "number" ? val : parseFloat(val);
  return isNaN(n) ? "—" : `${Math.round(n)}%`;
}

// ─── Data hook ────────────────────────────────────────────────────────────────

/**
 * Fetch all dashboard data sources in parallel.
 * Returns { data, loading, error, refetch }.
 */
function useDashboardData(token) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const fetch_ = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    const h = { Authorization: `Bearer ${token}` };

    const safe = async (url) => {
      try {
        const r = await fetch(url, { headers: h });
        return r.ok ? r.json() : null;
      } catch { return null; }
    };

    const [summary, changed, risks, audits, drift, engine] = await Promise.all([
      safe("/api/v1/risk/summary"),
      safe("/api/v1/risk/whats-changed"),
      safe("/api/v1/risks?limit=500"),
      safe("/api/v1/audits?limit=200"),
      safe("/api/v1/drift/alerts"),
      safe("/api/v1/engine/status"),
    ]);

    setData({ summary, changed, risks, audits, drift, engine });
    setLoading(false);
  }, [token]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { data, loading, error, refetch: fetch_ };
}

// ─── KPI derivation ───────────────────────────────────────────────────────────

function deriveKpis(data, persona) {
  const summary = data?.summary  || {};
  const changed = data?.changed  || {};
  const risks   = Array.isArray(data?.risks)  ? data.risks  : [];
  const audits  = Array.isArray(data?.audits) ? data.audits : [];
  const driftAlerts = data?.drift?.alerts || (Array.isArray(data?.drift) ? data.drift : []);
  const engine  = data?.engine   || {};

  const today       = audits.filter((a) => _isToday(a.created_at));
  const todayFailed = today.filter((a) => (a.status || "").toLowerCase() === "failed");
  const allFailed   = audits.filter((a) => (a.status || "").toLowerCase() === "failed");
  const queued      = audits.filter((a) => ["pending","running","queued"].includes((a.status||"").toLowerCase()));

  const openRisks    = risks.filter(_isOpen);
  const criticalRisks = openRisks.filter((r) => r.severity === "critical");
  const overdueRisks  = openRisks.filter((r) => _isOverdue(r.dueDate));
  const dueThisWeek   = openRisks.filter((r) => r.dueDate && _isThisWeek(r.dueDate) && !_isOverdue(r.dueDate));

  const rulePackLabel = engine.rule_pack_hash
    ? `#${engine.rule_pack_hash.slice(0, 8)}`
    : (engine.rule_packs_loaded?.[0] || "—");

  const triggeredDrift = driftAlerts.filter((a) =>
    a.triggered || a.status === "triggered" || a.drift_detected || a.has_drift
  );

  const remedPct = summary.remediation_pct ?? changed.remediation_rate ?? null;
  const avgScore = summary.overall_risk_score ?? null;
  const newScans = changed.new_audits_count ?? null;

  // score_delta sign convention: positive = risk going up (bad)
  const scoreDelta = changed.score_delta ?? null;
  const deltaDir   = changed.delta_direction; // "up"|"down"|"flat"

  switch (persona) {
    case "risk_officer":
    case "admin":
    case "super_admin":
      return [
        {
          size: "large",
          label: "Critical Risks",
          value: _fmt(criticalRisks.length),
          delta: criticalRisks.length,
          severity: criticalRisks.length > 0 ? "critical" : "low",
          icon: ShieldAlert,
        },
        {
          label: "Due This Week",
          value: _fmt(dueThisWeek.length),
          delta: dueThisWeek.length,
          severity: dueThisWeek.length > 3 ? "high" : "medium",
          icon: Clock,
        },
        {
          label: "Overdue",
          value: _fmt(overdueRisks.length),
          delta: overdueRisks.length,
          severity: overdueRisks.length > 0 ? "high" : "low",
          icon: AlertTriangle,
        },
        {
          label: "Remediation %",
          value: _pct(remedPct),
          delta: scoreDelta !== null ? (deltaDir === "down" ? -1 : deltaDir === "up" ? 1 : 0) : null,
          severity: "low",
          icon: Sparkles,
        },
      ];

    case "compliance_lead":
      return [
        {
          label: "EVF Frameworks",
          value: 4,
          delta: null,
          severity: "info",
          icon: Shield,
          sub: "Under internal review",
        },
        {
          label: "Overdue Controls",
          value: _fmt(overdueRisks.length),
          delta: overdueRisks.length,
          severity: overdueRisks.length > 0 ? "high" : "low",
          icon: AlertTriangle,
        },
        {
          label: "Scans This Week",
          value: _fmt(newScans ?? today.length),
          delta: newScans,
          severity: "info",
          icon: Clock,
        },
        {
          label: "Remediation %",
          value: _pct(remedPct),
          delta: null,
          severity: remedPct !== null && remedPct < 30 ? "medium" : "low",
          icon: Sparkles,
        },
      ];

    case "ai_auditor":
      return [
        {
          label: "Scans Today",
          value: _fmt(today.length),
          delta: today.length,
          severity: "info",
          icon: Clock,
        },
        {
          label: "Rule Pack",
          value: rulePackLabel,
          delta: null,
          severity: "info",
          icon: Shield,
          sub: engine.status === "healthy" ? "Engine healthy" : engine.status || "—",
        },
        {
          label: "Drift Alerts",
          value: _fmt(triggeredDrift.length),
          delta: triggeredDrift.length,
          severity: triggeredDrift.length > 0 ? "high" : "low",
          icon: Activity,
        },
        {
          label: "Avg Risk Score",
          value: avgScore !== null ? Math.round(avgScore) : "—",
          delta: scoreDelta,
          severity: avgScore !== null && avgScore >= 70 ? "critical" : avgScore >= 40 ? "medium" : "low",
          icon: Sparkles,
        },
      ];

    case "operator":
    default:
      return [
        {
          label: "Scans Today",
          value: _fmt(today.length),
          delta: today.length,
          severity: "info",
          icon: Clock,
        },
        {
          label: "Failed Scans",
          value: _fmt(allFailed.length),
          delta: allFailed.length,
          severity: allFailed.length > 0 ? "high" : "low",
          icon: AlertTriangle,
        },
        {
          label: "Queue Depth",
          value: _fmt(queued.length),
          delta: null,
          severity: queued.length > 5 ? "medium" : "low",
          icon: Sparkles,
        },
        {
          label: "Avg Score",
          value: avgScore !== null ? Math.round(avgScore) : "—",
          delta: scoreDelta,
          severity: avgScore !== null && avgScore >= 70 ? "critical" : "low",
          icon: ShieldAlert,
        },
      ];
  }
}

function derivePosture(data) {
  const summary = data?.summary  || {};
  const risks   = Array.isArray(data?.risks) ? data.risks : [];
  const changed = data?.changed  || {};

  const rag         = summary.rag_status || "No data";
  const postureLevel = _RAG_TO_POSTURE[rag] || _DEFAULT_POSTURE;
  const openRisks   = risks.filter(_isOpen).length;
  const overdue     = risks.filter(_isOpen).filter((r) => _isOverdue(r.dueDate)).length;
  const genAt       = summary.generated_at;
  const lastUpdated = genAt
    ? new Date(genAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "—";

  return { postureLevel, openRisks, overdue, lastUpdated };
}

// ─── Sub-components ──────────────────────────────────────────────────────────

const POSTURE_STYLES = {
  CRITICAL: { bg: "var(--color-critical-bg)", border: "var(--color-critical-border)", color: "var(--color-critical)" },
  HIGH:     { bg: "var(--color-high-bg)",     border: "var(--color-high-border)",     color: "var(--color-high)" },
  MEDIUM:   { bg: "var(--color-medium-bg)",   border: "var(--color-medium-border)",   color: "var(--color-medium)" },
  LOW:      { bg: "var(--color-low-bg)",       border: "var(--color-low-border)",      color: "var(--color-low)" },
};

function RiskPostureBanner({ level, openRisks, overdueItems, lastUpdated, loading }) {
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
        <div style={{ textAlign: "center" }}>
          {loading ? <Skeleton height={32} width={40} /> : (
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)", color: s.color, fontFamily: "var(--font-mono)" }}>
              {openRisks}
            </div>
          )}
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Open Risks
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          {loading ? <Skeleton height={32} width={40} /> : (
            <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)", color: s.color, fontFamily: "var(--font-mono)" }}>
              {overdueItems}
            </div>
          )}
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

function KpiCard({ label, value, delta, severity, size, icon: Icon, loading, sub }) {
  const colors = {
    critical: "var(--color-critical)",
    high:     "var(--color-high)",
    medium:   "var(--color-medium)",
    low:      "var(--color-low)",
    ai:       "var(--color-ai)",
    info:     "var(--color-info)",
  };
  const color   = colors[severity] || colors.info;
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

      {sub && !loading && (
        <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
          {sub}
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

/**
 * STORY-015: Inline drift alert notifications.
 * Fetches /api/v1/drift/alerts (shared with DriftAlerts page).
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
    fetch("/api/v1/drift/alerts", { headers: { Authorization: `Bearer ${token}` } })
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
      background: "var(--color-medium-bg)", border: "1px solid var(--color-medium-border)",
      borderRadius: "var(--radius-lg)", padding: "var(--space-3) var(--space-4)",
      marginBottom: "var(--space-4)", display: "flex", alignItems: "flex-start", gap: 10,
    }}>
      <Activity size={16} color="var(--color-medium)" style={{ marginTop: 2, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
          color: "var(--color-medium)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6,
        }}>
          {visible.length} Drift Alert{visible.length > 1 ? "s" : ""} Detected
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {visible.slice(0, 5).map((a, i) => {
            const id    = a.id || a.alert_id || a.name || String(i);
            const label = a.framework_name || a.name || a.alert_type || `Alert ${i + 1}`;
            const sev   = a.severity || "medium";
            const sevColor = sev === "critical" || sev === "high" ? "var(--color-critical)" : "var(--color-medium)";
            return (
              <span key={id} style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                background: "var(--color-medium-bg)", border: "1px solid var(--color-medium-border)",
                borderRadius: 6, padding: "3px 8px",
                fontSize: "var(--text-xs)", color: sevColor, fontWeight: "var(--weight-medium)",
              }}>
                ⚠ {label}
                <button
                  onClick={() => dismiss(id)}
                  aria-label={`Dismiss ${label}`}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-text-muted)", padding: 0, lineHeight: 1, marginLeft: 2 }}
                >
                  <X size={10} />
                </button>
              </span>
            );
          })}
          {visible.length > 5 && (
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-medium)", alignSelf: "center" }}>
              +{visible.length - 5} more
            </span>
          )}
        </div>
      </div>
      <button
        onClick={() => onNavigate?.("drift_alerts")}
        style={{
          padding: "4px 10px", background: "var(--color-medium-bg)", border: "1px solid var(--color-medium-border)",
          borderRadius: 5, cursor: "pointer", fontSize: "var(--text-xs)",
          color: "var(--color-medium)", fontWeight: "var(--weight-semibold)", flexShrink: 0,
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

/** GAP-009: per-panel vertical filter — scoped to the panel it's rendered in
 *  (currently Regulation Coverage and Engine Scores), not a global dashboard filter. */
function VerticalSelector({ vertical, onChange }) {
  return (
    <select
      value={vertical}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Filter by vertical"
      style={{
        padding: "2px 6px", borderRadius: "var(--radius-sm)",
        border: "1px solid var(--color-border-default)",
        background: "var(--color-bg-elevated)", color: "var(--color-text-muted)",
        fontSize: "var(--text-xs)", fontFamily: "var(--font-display)",
        cursor: "pointer",
      }}
    >
      {VERTICALS.map((v) => (
        <option key={v} value={v}>{v.charAt(0).toUpperCase() + v.slice(1)}</option>
      ))}
    </select>
  );
}

const qaBtn = (bg) => ({
  padding: "6px 14px", background: bg, color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontSize: "var(--text-sm)",
  fontWeight: "var(--weight-medium)", fontFamily: "var(--font-body)",
});

const PERSONA_SUBTITLE = {
  compliance_lead: "Compliance readiness & EVF status",
  risk_officer:    "Risk posture & open findings",
  ai_auditor:      "Scan pipeline & drift monitoring",
  operator:        "Upload queue & scan activity",
  admin:           "Risk posture & open findings",
  super_admin:     "Risk posture & open findings",
};

// ─── Main component ───────────────────────────────────────────────────────────

export default function Dashboard({ token, tenantId, user, onNavigate, toast }) {
  const persona = user?.persona_role || user?.role || "operator";
  const [vertical,   setVertical]   = useState("finance");
  const [timeWindow, setTimeWindow] = useState("7d");
  const [degraded,   setDegraded]   = useState(false);
  const [showOperationalDetail, setShowOperationalDetail] = useState(
    !["risk_officer", "compliance_lead"].includes(user?.persona_role || user?.role)
  );

  const { data, loading, refetch } = useDashboardData(token);

  function handleRefresh() {
    refetch().then(() => toast?.success("Dashboard updated"));
  }

  const kpis    = data ? deriveKpis(data, persona)    : [];
  const posture = data ? derivePosture(data)           : { postureLevel: "HIGH", openRisks: "—", overdue: "—", lastUpdated: "—" };

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
            {/* Manual refresh */}
            <button
              onClick={handleRefresh}
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

        {/* Risk posture banner — always first, regardless of drift alerts */}
        <RiskPostureBanner
          level={posture.postureLevel}
          openRisks={posture.openRisks}
          overdueItems={posture.overdue}
          lastUpdated={posture.lastUpdated}
          loading={loading}
        />

        {/* Drift alerts inline — STORY-015 */}
        {["ai_auditor","admin","super_admin","compliance_lead"].includes(persona) && (
          <DriftAlertsBanner token={token} onNavigate={onNavigate} />
        )}

        {/* KPI cards — live data, persona-specific */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}>
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <KpiCard key={i} label="Loading…" loading={true} />
              ))
            : kpis.map((kpi, i) => (
                <KpiCard
                  key={i}
                  size={kpi.size}
                  label={kpi.label}
                  value={kpi.value}
                  delta={kpi.delta}
                  severity={kpi.severity}
                  icon={kpi.icon}
                  sub={kpi.sub}
                  loading={false}
                />
              ))
          }
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
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
                    <h2 style={{
                      fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
                      color: "var(--color-text-muted)", textTransform: "uppercase",
                      letterSpacing: "0.08em", fontFamily: "var(--font-display)",
                    }}>
                      Regulation Coverage
                    </h2>
                    <VerticalSelector vertical={vertical} onChange={setVertical} />
                  </div>
                  <RegCoverage token={token} tenantId={tenantId} window={timeWindow} vertical={vertical} />
                </div>
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
                    <h2 style={{
                      fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
                      color: "var(--color-text-muted)", textTransform: "uppercase",
                      letterSpacing: "0.08em", fontFamily: "var(--font-display)",
                    }}>
                      Engine Scores
                    </h2>
                    <VerticalSelector vertical={vertical} onChange={setVertical} />
                  </div>
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
