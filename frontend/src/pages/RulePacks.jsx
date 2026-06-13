/**
 * Rule Packs — list, inspect, and manage SARO rule packs.
 */
import React, { useEffect, useState } from "react";

export default function RulePacks({ token }) {
  const [packs, setPacks]   = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/rules/packs", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setPacks(Array.isArray(d) ? d : d.packs || []); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token]);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1100 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📦 Rule Packs</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        SARO rule packs map AI risk categories to regulatory framework controls.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading rule packs…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 20 }}>
        {/* Pack list */}
        <div style={{ width: 280, flexShrink: 0 }}>
          {packs.map((pack) => (
            <div
              key={pack.id || pack.name}
              onClick={() => setSelected(pack)}
              style={{
                padding: "12px 14px", border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 8,
                cursor: "pointer", background: selected?.id === pack.id ? "#f0fdf4" : "#fff",
                borderColor: selected?.id === pack.id ? "#0d9488" : "#e5e7eb",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 13 }}>{pack.name || pack.id}</div>
              <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>v{pack.version} · {pack.framework}</div>
              <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
                {pack.rules?.length || 0} rules
              </div>
            </div>
          ))}
          {!loading && packs.length === 0 && (
            <div style={{ color: "#9ca3af", fontSize: 13 }}>No rule packs found.</div>
          )}
        </div>

        {/* Pack detail */}
        {selected ? (
          <div style={{ flex: 1, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
            <div style={{ marginBottom: 16 }}>
              <h2 style={{ fontSize: 18, marginBottom: 4 }}>{selected.name}</h2>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <span style={{ background: "#f0fdf4", color: "#166534", padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600 }}>
                  v{selected.version}
                </span>
                <span style={{ background: "#eff6ff", color: "#1d4ed8", padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600 }}>
                  {selected.framework}
                </span>
                {selected.vertical && (
                  <span style={{ background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600 }}>
                    {selected.vertical}
                  </span>
                )}
              </div>
            </div>

            {selected.description && (
              <p style={{ fontSize: 13, color: "#374151", marginBottom: 16 }}>{selected.description}</p>
            )}

            {selected.rules?.length > 0 && (
              <div>
                <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>Rules ({selected.rules.length})</h3>
                {selected.rules.map((rule, i) => {
                  const sevColor = rule.severity === "high" || rule.severity === "critical" ? "#dc2626" : rule.severity === "medium" ? "#ca8a04" : "#16a34a";
                  return (
                    <div key={i} style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: 12, marginBottom: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <code style={{ fontSize: 12, background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>{rule.id}</code>
                        <span style={{ background: sevColor + "20", color: sevColor, padding: "1px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                          {(rule.severity || "medium").toUpperCase()}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: "#374151" }}>{rule.description || rule.name}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 14 }}>
            Select a rule pack to view details
          </div>
        )}
      </div>
    </div>
  );
}
