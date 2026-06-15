import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Download, FileSpreadsheet, BarChart2, Target } from "lucide-react";
import { Button, EmptyState, PageHeader, Skeleton } from "../components/ui/index.jsx";

// Severity → colour (hex fallbacks so the charts render regardless of theme vars).
const SEV_COLOR = {
  critical: "#E24B4A", high: "#BA7517", medium: "#C99A2E", low: "#639922", info: "#0C447C",
};
const SEV_ORDER = ["critical", "high", "medium", "low", "info"];

function countBy(rows, key) {
  const out = {};
  for (const r of rows) {
    const k = (r[key] || "—").toString();
    out[k] = (out[k] || 0) + 1;
  }
  return out;
}

// Dependency-free horizontal bar chart (div widths, theme-aware).
function BarChart({ title, icon: Icon, data, colorFor }) {
  const entries = Object.entries(data);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div style={{
      background: "var(--color-bg-surface)",
      border: "1px solid var(--color-border-subtle)",
      borderRadius: "var(--radius-lg)", overflow: "hidden",
    }} className="chart-container">
      <div style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "center", gap: "var(--space-2)",
      }}>
        <Icon size={16} color="var(--color-text-muted)" />
        <h3 style={{
          fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)",
          color: "var(--color-text-primary)", fontFamily: "var(--font-display)",
        }}>{title}</h3>
      </div>
      <div style={{ padding: "var(--space-5)", minHeight: 160 }}>
        {entries.length === 0 ? (
          <EmptyState icon={<Icon />} title="No data yet"
            description="Run scans and create risks to populate this chart." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {entries.map(([label, value]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                <div style={{
                  width: 110, flexShrink: 0, fontSize: "var(--text-xs)",
                  color: "var(--color-text-muted)", textTransform: "capitalize",
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }} title={label}>{label}</div>
                <div style={{ flex: 1, background: "var(--color-bg-overlay)", borderRadius: 4, height: 18 }}>
                  <div style={{
                    width: `${(value / max) * 100}%`, height: "100%", borderRadius: 4,
                    background: colorFor ? colorFor(label) : "var(--color-info)",
                    minWidth: value > 0 ? 4 : 0, transition: "width var(--transition-fast)",
                  }} />
                </div>
                <div style={{
                  width: 28, textAlign: "right", fontSize: "var(--text-xs)",
                  fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)",
                }}>{value}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value }) {
  return (
    <div style={{
      background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)",
      borderRadius: "var(--radius-lg)", padding: "var(--space-4) var(--space-5)", flex: 1, minWidth: 130,
    }}>
      <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-bold)", color: "var(--color-text-primary)" }}>{value}</div>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{label}</div>
    </div>
  );
}

function toCsv(risks) {
  const cols = ["id", "title", "category", "severity", "owner", "status"];
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [cols.join(",")];
  for (const r of risks) lines.push(cols.map((c) => esc(r[c])).join(","));
  return lines.join("\n");
}

export default function Reports({ token }) {
  const [risks, setRisks]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch("/api/v1/risks", { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`${r.status}`);
      setRisks(await r.json());
    } catch (e) {
      setError(`Could not load risks from API: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const sevData = useMemo(() => {
    const c = countBy(risks, "severity");
    const ordered = {};
    for (const s of SEV_ORDER) if (c[s]) ordered[s] = c[s];
    for (const [k, v] of Object.entries(c)) if (!(k in ordered)) ordered[k] = v;
    return ordered;
  }, [risks]);
  const catData    = useMemo(() => countBy(risks, "category"), [risks]);
  const statusData = useMemo(() => countBy(risks, "status"), [risks]);

  const total    = risks.length;
  const open     = risks.filter((r) => !["Closed", "Dismissed", "Resolved"].includes(r.status)).length;
  const critHigh = risks.filter((r) => ["critical", "high"].includes(r.severity)).length;
  const closedPct = total ? Math.round(((total - open) / total) * 100) : 0;

  const exportCsv = useCallback(() => {
    const blob = new Blob([toCsv(risks)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "saro-risk-register.csv";
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  }, [risks]);

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Reports & Analytics"
        subtitle="Risk posture across the register — severity, category, and status"
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>Reports</span></>}
        actions={
          <Button variant="secondary" size="sm" onClick={exportCsv} disabled={!risks.length}>
            <FileSpreadsheet size={14} /> Export CSV
          </Button>
        }
      />

      <div style={{ padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {error && (
          <div style={{
            padding: "var(--space-3) var(--space-4)", borderRadius: "var(--radius-md)",
            background: "var(--color-danger-bg, #FCEBEB)", color: "var(--color-danger, #791F1F)",
            fontSize: "var(--text-sm)",
          }}>{error}</div>
        )}

        {loading ? (
          <Skeleton height={120} />
        ) : (
          <>
            <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap" }}>
              <Kpi label="Total risks" value={total} />
              <Kpi label="Open" value={open} />
              <Kpi label="Critical + High" value={critHigh} />
              <Kpi label="Closed / resolved" value={`${closedPct}%`} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)" }}>
              <BarChart title="Severity distribution" icon={BarChart2} data={sevData}
                colorFor={(label) => SEV_COLOR[label] || "var(--color-info)"} />
              <BarChart title="Risks by status" icon={Target} data={statusData} />
            </div>
            <BarChart title="Risks by category" icon={BarChart2} data={catData} />

            {/* Export buttons (header) are wired to a real CSV download; Download icon kept for affordance. */}
            <div style={{ display: "flex", gap: "var(--space-3)" }}>
              <Button variant="ghost" size="sm" onClick={exportCsv} disabled={!risks.length}>
                <Download size={14} /> Download register (CSV)
              </Button>
            </div>
          </>
        )}
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
