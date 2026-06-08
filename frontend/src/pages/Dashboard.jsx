import React, { useState, useEffect } from "react";
import { ShieldAlert, Clock, AlertTriangle, Sparkles, RefreshCw } from "lucide-react";
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

export default function Dashboard({ token, tenantId }) {
  const [vertical,   setVertical]   = useState("finance");
  const [timeWindow, setTimeWindow] = useState("7d");
  const [degraded,   setDegraded]   = useState(false);
  const [kpiLoading, setKpiLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState("just now");

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
        subtitle="Operational risk posture overview"
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

        {/* Risk posture banner — must be first thing visible */}
        <RiskPostureBanner
          level="HIGH"
          openRisks={47}
          overdueItems={12}
          lastUpdated={lastUpdated}
        />

        {/* KPI cards — ordered by business importance */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}>
          <KpiCard size="large" label="Critical Risks"   value={12}  delta={+3}  severity="critical" icon={ShieldAlert} loading={kpiLoading} />
          <KpiCard              label="Due This Week"     value={8}   delta={-1}  severity="high"     icon={Clock}       loading={kpiLoading} />
          <KpiCard              label="Controls Overdue"  value={5}   delta={0}   severity="medium"   icon={AlertTriangle} loading={kpiLoading} />
          <KpiCard              label="AI Pending"        value={23}  delta={+7}  severity="ai"       icon={Sparkles}    loading={kpiLoading} />
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
