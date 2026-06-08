/**
 * Coverage Gap — per-framework compliance gap analysis.
 */
import React, { useEffect, useState } from "react";

export default function CoverageGap({ token, tenantId }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [selectedFw, setSelectedFw] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    fetch(`/api/v1/compliance-matrix/coverage?tenant_id=${tenantId}&window=90d`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token, tenantId]);

  const frameworks = data?.frameworks || [];

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🗺️ Coverage Gap</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Per-framework compliance coverage analysis — identifies gaps in regulatory control coverage.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading coverage data…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {frameworks.length > 0 && (
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          {/* Framework list */}
          <div style={{ width: 260, flexShrink: 0 }}>
            {frameworks.map((fw) => {
              const pct = fw.coverage_pct || 0;
              const color = pct >= 80 ? "#16a34a" : pct >= 50 ? "#ca8a04" : "#dc2626";
              return (
                <div
                  key={fw.name}
                  onClick={() => setSelectedFw(fw)}
                  style={{
                    padding: 14, border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 8,
                    cursor: "pointer", background: selectedFw?.name === fw.name ? "#f0fdf4" : "#fff",
                    borderColor: selectedFw?.name === fw.name ? "#0d9488" : "#e5e7eb",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{fw.name}</span>
                    <span style={{ fontWeight: 700, color }}>{pct.toFixed(1)}%</span>
                  </div>
                  <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3 }}>
                    <div style={{ height: 6, width: `${pct}%`, background: color, borderRadius: 3, transition: "width 0.5s" }} />
                  </div>
                  {fw.gaps_count != null && (
                    <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>{fw.gaps_count} gaps identified</div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Gap detail */}
          {selectedFw ? (
            <div style={{ flex: 1 }}>
              <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
                <h2 style={{ fontSize: 16, marginBottom: 4 }}>{selectedFw.name}</h2>
                <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
                  Coverage: <strong style={{ color: "#0d9488" }}>{selectedFw.coverage_pct?.toFixed(1)}%</strong>
                  {selectedFw.controls_covered != null && selectedFw.controls_total != null && (
                    <> — {selectedFw.controls_covered}/{selectedFw.controls_total} controls covered</>
                  )}
                </div>

                {selectedFw.gaps?.length > 0 && (
                  <>
                    <h3 style={{ fontSize: 14, color: "#374151", marginBottom: 8 }}>Identified Gaps</h3>
                    {selectedFw.gaps.map((gap, i) => (
                      <div key={i} style={{ border: "1px solid #fee2e2", borderRadius: 6, padding: 10, marginBottom: 8, background: "#fff5f5" }}>
                        <div style={{ fontWeight: 600, fontSize: 13, color: "#b91c1c", marginBottom: 4 }}>{gap.control_id || gap.name}</div>
                        <div style={{ fontSize: 12, color: "#374151" }}>{gap.description || "No controls mapped to this requirement."}</div>
                      </div>
                    ))}
                  </>
                )}

                {(!selectedFw.gaps || selectedFw.gaps.length === 0) && (
                  <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 16, textAlign: "center", color: "#166534", fontSize: 13 }}>
                    ✓ No gaps identified for {selectedFw.name}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 14 }}>
              Select a framework to view gap details
            </div>
          )}
        </div>
      )}
    </div>
  );
}
