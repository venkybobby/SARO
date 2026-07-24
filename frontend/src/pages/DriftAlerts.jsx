/**
 * Drift Alerts — framework version drift detection.
 *
 * STORY-TAB-005: binds the real drift response (routers/rule_packs.py):
 *   GET /api/v1/rules/drift-alerts →
 *     {alerts:[{framework, current_version, latest_version, alert_type, message}],
 *      alert_count, current_versions:{fw:ver}, latest_known_versions:{fw:ver},
 *      checked_at}
 * The grid merges tracked frameworks with active packs, so a tracked framework
 * with NO pack is visible (that absence is itself a coverage signal).
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
  const current = data?.current_versions || {};
  const latestKnown = data?.latest_known_versions || {};
  // One card per framework SARO tracks or has a pack for — union, no drops.
  const frameworks = [...new Set([...Object.keys(latestKnown), ...Object.keys(current)])].sort();
  const checkedDate = data?.checked_at ? data.checked_at.slice(0, 10) : null;

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📡 Drift Alerts</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Framework version drift detection — compares active rule packs against the latest known framework versions.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13, marginBottom: 16 }}>
          ⚠ Could not reach drift-check endpoint ({error})
        </div>
      )}

      {/* Framework versions — tracked ∪ packed */}
      {!loading && !error && frameworks.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af", marginBottom: 16 }}>
          No tracked framework versions configured.
        </div>
      )}

      {!loading && !error && frameworks.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 15, marginBottom: 12 }}>Current Framework Versions</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
            {frameworks.map((fw) => {
              const cur = current[fw];
              const latest = latestKnown[fw];
              return (
                <div key={fw} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>{fw}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: cur ? "#111827" : "#9ca3af" }}>
                    {cur || "no pack"}
                  </div>
                  {latest && cur && latest !== cur && (
                    <div style={{ fontSize: 11, color: "#ca8a04", marginTop: 4 }}>Latest: {latest}</div>
                  )}
                  {!cur && latest && (
                    <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>Tracked at {latest}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* No-drift state — carries the check timestamp so the claim is fresh */}
      {!loading && !error && alerts.length === 0 && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 20, textAlign: "center", color: "#166534" }}>
          <div>✓ No drift alerts — all active rule packs match the latest known framework versions.</div>
          {checkedDate && (
            <div style={{ fontSize: 11, color: "#15803d", marginTop: 6 }}>Last checked: {checkedDate}</div>
          )}
        </div>
      )}

      {/* Alert cards — real fields only */}
      {alerts.map((alert, idx) => (
        <div key={idx} style={{ background: "#fff", border: "1px solid #fde68a", borderRadius: 8, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 16 }}>⚠️</span>
            <span style={{ fontWeight: 600, fontSize: 14 }}>
              {alert.message || `${alert.framework} — new version ${alert.latest_version} available (current: ${alert.current_version})`}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "#9ca3af" }}>
            {alert.framework}: {alert.current_version} → {alert.latest_version}
            {alert.alert_type && <> · {alert.alert_type.replace(/_/g, " ")}</>}
          </div>
        </div>
      ))}
    </div>
  );
}
