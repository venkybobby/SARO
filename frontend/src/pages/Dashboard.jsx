/**
 * Dashboard — S-201 Framework E2E Dashboard.
 * Calls real SARO API endpoints. All panels update on vertical/window change.
 */
import React, { useState, useEffect } from "react";
import FlowStrip    from "../components/FlowStrip";
import LiveFeed     from "../components/LiveFeed";
import MetricsRow   from "../components/MetricsRow";
import RegCoverage  from "../components/RegCoverage";
import EngineScores from "../components/EngineScores";

const VERTICALS = ["finance", "healthcare", "legal", "government"];
const WINDOWS   = ["7d", "30d", "90d"];

export default function Dashboard({ token, tenantId }) {
  const [vertical, setVertical] = useState("finance");
  const [timeWindow, setTimeWindow] = useState("7d"); // renamed from 'window' to avoid global shadowing
  const [degraded, setDegraded] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      if (e.reason?.message?.includes("503") || e.reason?.message?.includes("502")) {
        setDegraded(true);
      }
    };
    window.addEventListener("unhandledrejection", handler);
    return () => window.removeEventListener("unhandledrejection", handler);
  }, []);

  if (!token) {
    return <div style={{ padding: 24, color: "#6b7280" }}>Please log in to view the dashboard.</div>;
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      {degraded && (
        <div style={{ background: "#fef3c7", border: "1px solid #f59e0b", borderRadius: 6, padding: 8, marginBottom: 16 }}>
          ⚠ API degraded — some panels may show stale data
        </div>
      )}

      {/* Header + controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>SARO Framework Dashboard</h1>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {VERTICALS.map((v) => (
            <button
              key={v}
              onClick={() => setVertical(v)}
              style={{
                padding: "4px 12px", borderRadius: 20,
                border: "1px solid #d1d5db",
                background: vertical === v ? "#0d9488" : "#fff",
                color: vertical === v ? "#fff" : "#374151",
                cursor: "pointer", fontSize: 13,
              }}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
        </div>
        <select
          value={timeWindow}
          onChange={(e) => setTimeWindow(e.target.value)}
          style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #d1d5db" }}
        >
          {WINDOWS.map((w) => (
            <option key={w} value={w}>{w === "7d" ? "7 days" : w === "30d" ? "30 days" : "90 days"}</option>
          ))}
        </select>
      </div>

      {/* KPI cards */}
      <MetricsRow token={token} />

      {/* Pipeline status */}
      <div style={{ margin: "20px 0" }}>
        <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>PIPELINE STATUS</h3>
        <FlowStrip token={token} />
      </div>

      {/* Lower panels */}
      <div style={{ display: "flex", gap: 20, marginTop: 20, flexWrap: "wrap" }}>
        <div style={{ flex: 2, minWidth: 280 }}>
          <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>LIVE AUDIT FEED</h3>
          <LiveFeed token={token} tenantId={tenantId} />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>REGULATION COVERAGE</h3>
          <RegCoverage token={token} tenantId={tenantId} window={timeWindow} vertical={vertical} />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>ENGINE SCORES</h3>
          <EngineScores token={token} tenantId={tenantId} vertical={vertical} />
        </div>
      </div>
    </div>
  );
}
