/**
 * RegCoverage — per-framework compliance coverage bars with EVF validation badge.
 * Calls GET /api/v1/compliance_matrix — no hardcoded data.
 * Each framework bar now includes the EVF tier label returned by the API
 * (evf_tier: "tier_1"|"tier_2"|"tier_3", evf_label, evf_qco_reference).
 */
import React, { useEffect, useState } from "react";
import { fetchComplianceCoverage } from "../api/saro";

// GAP-009: accept vertical prop so dashboard vertical switcher filters this panel
export default function RegCoverage({ token, tenantId, window = "7d", vertical = null }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    fetchComplianceCoverage(token, tenantId, window, vertical)
      .then(setData)
      .catch(() => setData(null));
  }, [token, tenantId, window, vertical]);

  if (!data?.frameworks) return <div style={{ color: "#9ca3af" }}>Loading coverage…</div>;

  return (
    <div>
      {data.frameworks.map((fw) => (
        <div key={fw.name} style={{ marginBottom: 14 }}>
          {/* Framework name + coverage % */}
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
            <span>{fw.name}</span>
            <span>{fw.coverage_pct?.toFixed(1)}%</span>
          </div>

          {/* Coverage bar */}
          <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3, marginTop: 4 }}>
            <div
              style={{
                height: 6,
                width: `${fw.coverage_pct || 0}%`,
                background: "#0d9488",
                borderRadius: 3,
                transition: "width 0.5s",
              }}
            />
          </div>

          {/* EVF Validation tier badge — FR-EVF-11 */}
          {fw.evf_tier && <EvfTierBadge tier={fw.evf_tier} label={fw.evf_label} qcoRef={fw.evf_qco_reference} />}
        </div>
      ))}
    </div>
  );
}

/** Renders a compact EVF validation tier pill under each framework bar. */
function EvfTierBadge({ tier, label, qcoRef }) {
  const config = {
    tier_1: { bg: "#14532d", color: "#4ade80", text: "✓ QCO Issued" },
    tier_2: { bg: "#451a03", color: "#fbbf24", text: "⏳ Under Review" },
    tier_3: { bg: "#1e293b", color: "#64748b", text: "🔒 Internal Only" },
  }[tier] ?? { bg: "#1e293b", color: "#64748b", text: "Unknown" };

  return (
    <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          background: config.bg,
          color: config.color,
          fontSize: 10,
          fontWeight: 700,
          padding: "1px 7px",
          borderRadius: 10,
          letterSpacing: "0.04em",
          whiteSpace: "nowrap",
        }}
        title={label || ""}
      >
        {config.text}
      </span>
      {qcoRef && (
        <span style={{ fontSize: 10, color: "#64748b", fontFamily: "monospace" }}>
          {qcoRef}
        </span>
      )}
    </div>
  );
}
