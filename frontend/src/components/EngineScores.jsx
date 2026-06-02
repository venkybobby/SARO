/**
 * EngineScores — per-gate engine scores from GET /api/v1/risk_dashboard.
 * No hardcoded values.
 */
import React, { useEffect, useState } from "react";
import { fetchRiskDashboard } from "../api/saro";

// GAP-009: accept vertical prop so dashboard vertical switcher filters this panel
export default function EngineScores({ token, tenantId, vertical = null }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    fetchRiskDashboard(token, tenantId, vertical)
      .then(setData)
      .catch(() => setData(null));
  }, [token, tenantId, vertical]);

  if (!data) return <div style={{ color: "#9ca3af" }}>Loading engine scores…</div>;

  return (
    <div>
      {(data.gate_scores || []).map((gate) => (
        <div key={gate.name} style={{ marginBottom: 8, fontSize: 13 }}>
          <span style={{ fontWeight: 600 }}>{gate.name}:</span>{" "}
          {gate.score != null ? (gate.score * 100).toFixed(0) + "%" : "—"}
        </div>
      ))}
    </div>
  );
}
