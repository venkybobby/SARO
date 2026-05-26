/**
 * MetricsRow — top-level KPI cards from GET /api/v1/dashboard.
 * Values come from the live API, never hardcoded.
 */
import React, { useEffect, useState } from "react";
import { fetchDashboardMetrics } from "../api/saro";

function Card({ label, value, sub }) {
  return (
    <div style={{ flex: 1, padding: 16, background: "#f9fafb", borderRadius: 8, margin: 4 }}>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value ?? "—"}</div>
      <div style={{ fontWeight: 600, fontSize: 13, marginTop: 4 }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function MetricsRow({ token }) {
  const [metrics, setMetrics] = useState(null);
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      try {
        const data = await fetchDashboardMetrics(token);
        setMetrics(data);
        setDegraded(false);
      } catch {
        setDegraded(true);
      }
    };
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [token]);

  if (degraded) {
    return (
      <div style={{ background: "#fef3c7", padding: 8, borderRadius: 6, marginBottom: 8 }}>
        ⚠ Dashboard API unavailable — showing last known data
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 8 }}>
      <Card label="Total Audits" value={metrics?.total_audits} />
      <Card label="Avg Risk Score" value={metrics?.avg_risk_score?.toFixed(2)} />
      <Card label="Open Findings" value={metrics?.open_findings} />
      <Card label="Remediations" value={metrics?.remediations_done} />
    </div>
  );
}
