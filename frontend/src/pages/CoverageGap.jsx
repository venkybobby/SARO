/**
 * Coverage Gap — per-framework compliance coverage analysis.
 *
 * STORY-TAB-003: binds the real coverage API (routers/compliance_matrix.py):
 *   GET /api/v1/compliance-matrix/coverage →
 *     {frameworks:[{framework, total_rules, covered, partial, not_covered,
 *                   coverage_pct, last_updated}],
 *      overall_coverage_pct, framework_count, total_rules}
 * The gap signal is the API's own not_covered/partial counts — no fabricated
 * per-control gap list (a per-rule drill-down needs a new endpoint).
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
        Per-framework compliance coverage analysis — identifies rules not yet covered by your scanning regime.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading coverage data…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {!loading && !error && frameworks.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          No coverage data available yet — run scans to populate the compliance matrix.
        </div>
      )}

      {!loading && !error && frameworks.length > 0 && (
        <>
          {/* Overall rollup — straight from the API */}
          <div style={{
            background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
            padding: "12px 16px", marginBottom: 16,
            display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8,
          }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>
              Overall coverage: {Number(data.overall_coverage_pct).toFixed(1)}%
            </span>
            <span style={{ fontSize: 12, color: "#9ca3af" }}>
              {data.framework_count} frameworks · {data.total_rules} rules
            </span>
          </div>

          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            {/* Framework list */}
            <div style={{ width: 260, flexShrink: 0 }}>
              {frameworks.map((fw) => {
                const pct = fw.coverage_pct || 0;
                const color = pct >= 80 ? "#16a34a" : pct >= 50 ? "#ca8a04" : "#dc2626";
                const isSelected = selectedFw?.framework === fw.framework;
                return (
                  <div
                    key={fw.framework}
                    onClick={() => setSelectedFw(fw)}
                    style={{
                      padding: 14, border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 8,
                      cursor: "pointer", background: isSelected ? "#f0fdf4" : "#fff",
                      borderColor: isSelected ? "#0d9488" : "#e5e7eb",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, gap: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{fw.framework}</span>
                      <span style={{ fontWeight: 700, color }}>{pct.toFixed(1)}%</span>
                    </div>
                    <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3 }}>
                      <div style={{ height: 6, width: `${pct}%`, background: color, borderRadius: 3, transition: "width 0.5s" }} />
                    </div>
                    {fw.not_covered > 0 && (
                      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>
                        {fw.not_covered} rule{fw.not_covered === 1 ? "" : "s"} not covered
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Coverage detail */}
            {selectedFw ? (
              <div style={{ flex: 1 }}>
                <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
                  <h2 style={{ fontSize: 16, marginBottom: 4 }}>{selectedFw.framework}</h2>
                  <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
                    Coverage: <strong style={{ color: "#0d9488" }}>{selectedFw.coverage_pct?.toFixed(1)}%</strong>
                    {selectedFw.last_updated && <> — Last updated: {selectedFw.last_updated}</>}
                  </div>

                  {/* Breakdown — the API's own counts */}
                  <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
                    <span style={{ background: "#f0fdf4", color: "#166534", padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
                      Covered: {selectedFw.covered}
                    </span>
                    <span style={{ background: "#fef3c7", color: "#92400e", padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
                      Partial: {selectedFw.partial}
                    </span>
                    <span style={{ background: "#fee2e2", color: "#b91c1c", padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
                      Not covered: {selectedFw.not_covered}
                    </span>
                  </div>

                  {selectedFw.not_covered > 0 ? (
                    <div style={{ border: "1px solid #fee2e2", borderRadius: 6, padding: 12, background: "#fff5f5", fontSize: 13, color: "#b91c1c", fontWeight: 600 }}>
                      {selectedFw.not_covered} of {selectedFw.total_rules} rules not covered for this framework.
                    </div>
                  ) : selectedFw.partial > 0 ? (
                    <div style={{ border: "1px solid #fef3c7", borderRadius: 6, padding: 12, background: "#fffbeb", fontSize: 13, color: "#92400e", fontWeight: 600 }}>
                      {selectedFw.partial} of {selectedFw.total_rules} rules only partially covered.
                    </div>
                  ) : (
                    <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 16, textAlign: "center", color: "#166534", fontSize: 13 }}>
                      ✓ All {selectedFw.total_rules} rules covered for {selectedFw.framework}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 14, minHeight: 120 }}>
                Select a framework to view its coverage breakdown
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
