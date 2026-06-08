/**
 * Risk Summary — board-level risk officer view.
 * Key metrics, top findings, what's changed, vendor risk.
 */
import React, { useEffect, useState } from "react";

const RAG_COLORS = { green: "#16a34a", amber: "#ca8a04", red: "#dc2626" };

function RagBadge({ rag }) {
  const color = RAG_COLORS[(rag || "amber").toLowerCase()] || "#6b7280";
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, padding: "4px 14px", borderRadius: 12, fontWeight: 700, fontSize: 14 }}>
      {(rag || "AMBER").toUpperCase()}
    </span>
  );
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div style={{ flex: 1, minWidth: 160, padding: 16, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8 }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || "#111827" }}>{value ?? "—"}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginTop: 4 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function RiskSummary({ token, tenantId }) {
  const [summary, setSummary] = useState(null);
  const [findings, setFindings] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) return;
    const h = { Authorization: `Bearer ${token}` };

    fetch(`/api/v1/risk_dashboard${tenantId ? `?tenant_id=${tenantId}` : ""}`, { headers: h })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => {
        setSummary(d.summary || d);
        setFindings(d.top_findings || []);
      })
      .catch((e) => setError(`Risk dashboard unavailable (${e})`));

    fetch(`/api/v1/vendor-risk${tenantId ? `?tenant_id=${tenantId}` : ""}`, { headers: h })
      .then((r) => r.ok ? r.json() : [])
      .then((d) => setVendors(Array.isArray(d) ? d : d.vendors || []))
      .catch(() => {});
  }, [token, tenantId]);

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1100 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📊 Risk Summary</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>Board-level risk officer view — overall RAG status, trends, and top findings.</p>

      {/* KPI bar */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160, padding: 16, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>Overall RAG</div>
          <RagBadge rag={summary?.rag_status} />
        </div>
        <KpiCard label="90-Day Trend" value={summary?.trend_label || "—"} sub="Direction of avg risk score" />
        <KpiCard label="Remediation %" value={summary?.remediation_rate != null ? `${(summary.remediation_rate * 100).toFixed(0)}%` : "—"} />
        <KpiCard label="Open Findings" value={summary?.open_findings} />
        <KpiCard label="Avg Risk Score" value={summary?.avg_risk_score?.toFixed(1)} />
      </div>

      {/* Top Findings */}
      {findings.length > 0 && (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 20 }}>
          <h2 style={{ fontSize: 15, marginBottom: 12 }}>Top Findings</h2>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                <th style={{ textAlign: "left", padding: "6px 8px", color: "#6b7280" }}>Finding</th>
                <th style={{ textAlign: "left", padding: "6px 8px", color: "#6b7280" }}>Severity</th>
                <th style={{ textAlign: "left", padding: "6px 8px", color: "#6b7280" }}>Framework</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, i) => {
                const sevColor = f.severity === "high" || f.severity === "critical" ? "#dc2626" : f.severity === "medium" ? "#ca8a04" : "#16a34a";
                return (
                  <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "8px 8px" }}>{f.description || f.title || "—"}</td>
                    <td style={{ padding: "8px 8px" }}>
                      <span style={{ background: sevColor + "20", color: sevColor, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                        {(f.severity || "—").toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: "8px 8px", color: "#6b7280" }}>{f.framework || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Vendor Risk */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
        <h2 style={{ fontSize: 15, marginBottom: 12 }}>🏢 Vendor Risk</h2>
        {vendors.length === 0 ? (
          <div style={{ color: "#9ca3af", fontSize: 13 }}>No vendor risk data available.</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
            {vendors.map((v, i) => (
              <div key={i} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{v.name || v.vendor}</div>
                <RagBadge rag={v.rag_status || v.risk_level} />
                {v.last_audit && <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 6 }}>Last audit: {v.last_audit}</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginTop: 20, padding: 10, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: 11, color: "#64748b" }}>
        Evidence supporting NIST AI RMF Measure 2.5 — human review required before regulatory submission.
      </div>
    </div>
  );
}
