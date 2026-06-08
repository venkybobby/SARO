/**
 * Evaluations — saro-data-framework run history (TruthfulQA, PII, toxicity batch jobs).
 */
import React, { useEffect, useState } from "react";

export default function Evaluations({ token }) {
  const [evals, setEvals]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/evaluations", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setEvals(Array.isArray(d) ? d : d.items || []); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token]);

  const STATUS_STYLE = {
    completed: { bg: "#d1fae5", color: "#065f46" },
    running:   { bg: "#dbeafe", color: "#1d4ed8" },
    failed:    { bg: "#fee2e2", color: "#991b1b" },
    pending:   { bg: "#f3f4f6", color: "#6b7280" },
  };

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🧪 Evaluations</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Batch evaluation run history from the saro-data-framework — TruthfulQA, PII detection, toxicity analysis.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading evaluations…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}
      {!loading && !error && evals.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          No evaluation runs yet. Trigger a batch job via the saro-data-framework.
        </div>
      )}

      {evals.map((ev) => {
        const st = STATUS_STYLE[ev.status] || STATUS_STYLE.pending;
        return (
          <div key={ev.id || ev.run_id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{ev.name || ev.eval_type || "Evaluation Run"}</span>
                  <span style={{ background: st.bg, color: st.color, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    {ev.status}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 20, fontSize: 12, color: "#9ca3af", flexWrap: "wrap" }}>
                  {ev.eval_type && <span>Type: {ev.eval_type}</span>}
                  {ev.sample_count != null && <span>Samples: {ev.sample_count}</span>}
                  {ev.created_at && <span>Started: {ev.created_at.slice(0, 16)}</span>}
                  {ev.completed_at && <span>Completed: {ev.completed_at.slice(0, 16)}</span>}
                </div>
                {ev.metrics && (
                  <div style={{ marginTop: 10, display: "flex", gap: 12, flexWrap: "wrap" }}>
                    {Object.entries(ev.metrics).map(([k, v]) => (
                      <div key={k} style={{ padding: "8px 12px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6 }}>
                        <div style={{ fontSize: 11, color: "#9ca3af", textTransform: "uppercase" }}>{k.replace(/_/g, " ")}</div>
                        <div style={{ fontSize: 16, fontWeight: 700 }}>
                          {typeof v === "number" ? (v < 1 ? `${(v * 100).toFixed(1)}%` : v.toFixed(2)) : v}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
