/**
 * Rule Packs — list, inspect, and manage SARO rule packs.
 *
 * STORY-TAB-006: two-endpoint master/detail (routers/rule_packs.py):
 *   GET /api/v1/rules/packs             → {packs:[summary w/ rule_count], total}
 *   GET /api/v1/rules/packs/{framework} → summary + rules[] + description
 * The list stays light; selecting a pack fetches its rules.
 */
import React, { useEffect, useState } from "react";
import DriftAlerts from "./DriftAlerts.jsx";

export default function RulePacks({ token }) {
  const [packs, setPacks]   = useState([]);
  const [selected, setSelected] = useState(null);      // framework id of the selection
  const [detail, setDetail] = useState(null);          // fetched detail for `selected`
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/rules/packs", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setPacks(Array.isArray(d) ? d : d.packs || []); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token]);

  useEffect(() => {
    if (!token || !selected) return;
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    fetch(`/api/v1/rules/packs/${encodeURIComponent(selected)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => {
        // Guard against a stale response landing after the selection changed.
        if (cancelled) return;
        setDetail(d);
        setDetailLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setDetailError(`${e}`);
        setDetailLoading(false);
      });
    return () => { cancelled = true; };
  }, [token, selected]);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1100 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📦 Rule Packs</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        SARO rule packs map AI risk categories to regulatory framework controls.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading rule packs…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ Failed to load rule packs ({error})
        </div>
      )}

      {/* STORY-TAB-008: Drift Alerts folded in — the original component, hosted
          as a section; its fetch/error lifecycle is independent of the list. */}
      <div style={{ margin: "0 0 24px" }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>Framework Drift</h2>
        <DriftAlerts token={token} embedded />
      </div>

      <div style={{ display: "flex", gap: 20 }}>
        {/* Pack list — light summaries */}
        <div style={{ width: 280, flexShrink: 0 }}>
          {packs.map((pack) => (
            <div
              key={pack.framework}
              onClick={() => setSelected(pack.framework)}
              style={{
                padding: "12px 14px", border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 8,
                cursor: "pointer", background: selected === pack.framework ? "#f0fdf4" : "#fff",
                borderColor: selected === pack.framework ? "#0d9488" : "#e5e7eb",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 13 }}>{pack.name || pack.framework}</div>
              <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>v{pack.version} · {pack.framework}</div>
              <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
                {pack.rule_count ?? 0} rules
              </div>
            </div>
          ))}
          {!loading && packs.length === 0 && (
            <div style={{ color: "#9ca3af", fontSize: 13 }}>No rule packs found.</div>
          )}
        </div>

        {/* Pack detail — fetched per selection */}
        {selected ? (
          <div style={{ flex: 1, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
            {detailLoading && <div style={{ color: "#9ca3af" }}>Loading pack detail…</div>}
            {detailError && (
              <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
                ⚠ Failed to load rule pack detail ({detailError})
              </div>
            )}
            {detail && !detailLoading && !detailError && (
              <>
                <div style={{ marginBottom: 16 }}>
                  <h2 style={{ fontSize: 18, marginBottom: 4 }}>{detail.name}</h2>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ background: "#f0fdf4", color: "#166534", padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600 }}>
                      v{detail.version}
                    </span>
                    <span style={{ background: "#eff6ff", color: "#1d4ed8", padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600 }}>
                      {detail.framework}
                    </span>
                    {detail.status && (
                      <span style={{ background: "#f3f4f6", color: "#374151", padding: "2px 8px", borderRadius: 10, fontSize: 12, fontWeight: 600 }}>
                        {detail.status}
                      </span>
                    )}
                    {detail.last_updated && (
                      <span style={{ fontSize: 12, color: "#9ca3af", alignSelf: "center" }}>
                        Updated {detail.last_updated}
                      </span>
                    )}
                  </div>
                </div>

                {detail.description && (
                  <p style={{ fontSize: 13, color: "#374151", marginBottom: 16 }}>{detail.description}</p>
                )}

                {detail.rules?.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>Rules ({detail.rules.length})</h3>
                    {detail.rules.map((rule, i) => {
                      const sev = (rule.severity || "medium").toLowerCase();
                      const sevColor = sev === "high" || sev === "critical" ? "#dc2626" : sev === "medium" ? "#ca8a04" : "#16a34a";
                      return (
                        <div key={rule.id || i} style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: 12, marginBottom: 8 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                            <code style={{ fontSize: 12, background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>{rule.id}</code>
                            <span style={{ background: sevColor + "20", color: sevColor, padding: "1px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                              {sev.toUpperCase()}
                            </span>
                          </div>
                          <div style={{ fontSize: 13, color: "#374151" }}>{rule.description || rule.name}</div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {detail.changelog?.length > 0 && (
                  <div>
                    <h3 style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>Changelog</h3>
                    {detail.changelog.map((entry, i) => (
                      <div key={i} style={{ fontSize: 12, color: "#374151", marginBottom: 6 }}>
                        <strong>v{entry.version}</strong>
                        {entry.date && <span style={{ color: "#9ca3af" }}> · {entry.date}</span>}
                        {Array.isArray(entry.changes) && (
                          <ul style={{ margin: "2px 0 0", padding: "0 0 0 16px" }}>
                            {entry.changes.map((c, j) => <li key={j}>{c}</li>)}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 14, minHeight: 120 }}>
            Select a rule pack to view its rules
          </div>
        )}
      </div>
    </div>
  );
}
