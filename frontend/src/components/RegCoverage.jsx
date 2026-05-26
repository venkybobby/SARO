/**
 * RegCoverage — per-framework compliance coverage bars.
 * Calls GET /api/v1/compliance-matrix/coverage — no hardcoded data.
 */
import React, { useEffect, useState } from "react";
import { fetchComplianceCoverage } from "../api/saro";

export default function RegCoverage({ token, tenantId, window = "7d" }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    fetchComplianceCoverage(token, tenantId, window)
      .then(setData)
      .catch(() => setData(null));
  }, [token, tenantId, window]);

  if (!data?.frameworks) return <div style={{ color: "#9ca3af" }}>Loading coverage…</div>;

  return (
    <div>
      {data.frameworks.map((fw) => (
        <div key={fw.name} style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
            <span>{fw.name}</span>
            <span>{fw.coverage_pct?.toFixed(1)}%</span>
          </div>
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
        </div>
      ))}
    </div>
  );
}
