import React, { useState } from "react";
import { Download, FileSpreadsheet, Share2, BarChart2, TrendingUp, Target, Grid } from "lucide-react";
import { Button, EmptyState, PageHeader, Skeleton } from "../components/ui/index.jsx";

const DATE_PRESETS = ["Last 7 days", "Last 30 days", "Last quarter", "Year to date", "Custom"];

function ExportMenu({ onExportPDF, onExportCSV, onShareLink }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <Button variant="secondary" size="sm" onClick={() => setOpen((v) => !v)}>
        <Download size={13} /> Export
      </Button>
      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 99 }} onClick={() => setOpen(false)} />
          <div style={{
            position: "absolute", top: "calc(100% + 4px)", right: 0,
            background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
            borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-md)",
            zIndex: "var(--z-dropdown)", minWidth: 180, overflow: "hidden",
          }}>
            {[
              { label: "Export as PDF",   icon: <Download size={14} />,       onClick: onExportPDF },
              { label: "Export as CSV",   icon: <FileSpreadsheet size={14} />, onClick: onExportCSV },
              { label: "Copy share link", icon: <Share2 size={14} />,          onClick: onShareLink },
            ].map((item) => (
              <button key={item.label} onClick={() => { item.onClick?.(); setOpen(false); }} style={{
                display: "flex", alignItems: "center", gap: "var(--space-3)",
                width: "100%", padding: "var(--space-3) var(--space-4)",
                background: "none", border: "none", cursor: "pointer",
                color: "var(--color-text-primary)", fontSize: "var(--text-sm)",
                fontFamily: "var(--font-body)", textAlign: "left",
                transition: "background var(--transition-fast)",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-bg-overlay)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
              >
                <span style={{ color: "var(--color-text-muted)" }}>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ChartPlaceholder({ title, type, icon: Icon, loading }) {
  return (
    <div style={{
      background: "var(--color-bg-surface)",
      border: "1px solid var(--color-border-subtle)",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
    }} className="chart-container">
      {/* Chart header */}
      <div style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Icon size={16} color="var(--color-text-muted)" />
          <h3 style={{
            fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)",
            color: "var(--color-text-primary)", fontFamily: "var(--font-display)",
          }}>
            {title}
          </h3>
        </div>
        <ExportMenu
          onExportPDF={() => {}}
          onExportCSV={() => {}}
          onShareLink={() => {}}
        />
      </div>
      {/* Chart body */}
      <div style={{ padding: "var(--space-5)", minHeight: 200 }}>
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <Skeleton height={20} width="60%" />
            <Skeleton height={120} />
            <Skeleton height={16} width="40%" />
          </div>
        ) : (
          <EmptyState
            icon={<Icon />}
            title={`${type} chart`}
            description="Connect a charting library (Recharts, Chart.js) to render live data here."
          />
        )}
      </div>
    </div>
  );
}

export default function Reports({ token }) {
  const [datePreset, setDatePreset] = useState("Last 30 days");
  const [loading]                   = useState(false);

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Reports & Analytics"
        subtitle="Risk trends, control coverage, and compliance posture over time"
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>Reports</span></>}
        actions={<ExportMenu onExportPDF={() => {}} onExportCSV={() => {}} onShareLink={() => {}} />}
      />

      {/* Toolbar */}
      <div className="report-toolbar" style={{
        padding: "var(--space-4) var(--space-6)",
        borderBottom: "1px solid var(--color-border-subtle)",
        background: "var(--color-bg-surface)",
        display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
          {DATE_PRESETS.map((p) => (
            <button
              key={p}
              onClick={() => setDatePreset(p)}
              style={{
                padding: "4px 12px", borderRadius: 999,
                border: `1px solid ${datePreset === p ? "var(--color-info)" : "var(--color-border-default)"}`,
                background: datePreset === p ? "var(--color-info-bg)" : "transparent",
                color: datePreset === p ? "var(--color-info)" : "var(--color-text-muted)",
                fontSize: "var(--text-xs)", cursor: "pointer",
                fontFamily: "var(--font-display)", fontWeight: "var(--weight-medium)",
                transition: "all var(--transition-fast)",
              }}
            >
              {p}
            </button>
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={() => setDatePreset("Last 30 days")}>
          Clear filters
        </Button>
      </div>

      <div style={{ padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {/* Top row: Trend + Distribution */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "var(--space-5)" }}>
          <ChartPlaceholder title="Risk trend over time"    type="Line"             icon={TrendingUp} loading={loading} />
          <ChartPlaceholder title="Severity distribution"   type="Stacked bar"      icon={BarChart2}  loading={loading} />
        </div>
        {/* Bottom row: Category + Coverage */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)" }}>
          <ChartPlaceholder title="Risks by category"       type="Horizontal bar"   icon={BarChart2}  loading={loading} />
          <ChartPlaceholder title="Control coverage"        type="Gauge / progress" icon={Target}     loading={loading} />
        </div>
        {/* Risk heatmap full width */}
        <ChartPlaceholder title="Risk heatmap (likelihood × impact)" type="Matrix / heatmap" icon={Grid} loading={loading} />
      </div>

      {/* Required disclaimer per COMPLIANCE_CLAIMS_MATRIX.md */}
      <div style={{
        margin: "0 var(--space-6) var(--space-6)",
        padding: "var(--space-3) var(--space-4)",
        background: "var(--color-bg-surface)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-md)",
        fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: 1.6,
      }}>
        <em>
          This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification,
          legal advice, or compliance approval. Human review and sign-off by qualified personnel is required
          before any regulatory submission.
        </em>
      </div>
    </div>
  );
}
