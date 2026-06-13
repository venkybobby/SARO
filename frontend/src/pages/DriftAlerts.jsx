/**
 * Drift Alerts — framework version drift detection and affected rule packs.
 */
import React, { useEffect, useState } from "react";

export default function DriftAlerts({ token }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/rules/drift-alerts", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token]);

  const alerts = data?.alerts || [];
  const versions = data?.framework_versions || [];

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📡 Drift Alerts</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Framework version drift detection — new versions, affected rule packs, and what changed.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13, marginBottom: 16 }}>
          ⚠ Could not reach drift-check endpoint ({error})
        </div>
      )}

      {/* Framework versions */}
      {versions.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 15, marginBottom: 12 }}>Current Framework Versions</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
            {versions.map((fw) => (
              <div key={fw.name} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, textAlign: "center" }}>
                <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>{fw.name}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "#111827" }}>{fw.current_version || "—"}</div>
                {fw.latest_version && fw.latest_version !== fw.current_version && (
                  <div style={{ fontSize: 11, color: "#ca8a04", marginTop: 4 }}>Latest: {fw.latest_version}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts */}
      {!loading && alerts.length === 0 && !error && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 20, textAlign: "center", color: "#166534" }}>
          ✓ No drift alerts — all framework versions are current.
        </div>
      )}

      {alerts.map((alert, idx) => (
        <div key={idx} style={{ background: "#fff", border: "1px solid #fde68a", borderRadius: 8, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 16 }}>⚠️</span>
            <span style={{ fontWeight: 600, fontSize: 14 }}>
              {alert.framework} — new version {alert.latest_version} available (current: {alert.current_version})
            </span>
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 8 }}>
            {alert.what_changed?.length > 0 && (
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", marginBottom: 4 }}>What Changed</div>
                <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 13 }}>
                  {alert.what_changed.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            {alert.affected_rule_packs?.length > 0 && (
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", marginBottom: 4 }}>Affected Rule Packs</div>
                <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 13 }}>
                  {alert.affected_rule_packs.map((p, i) => <li key={i} style={{ fontFamily: "monospace" }}>{p}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
