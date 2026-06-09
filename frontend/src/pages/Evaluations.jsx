/**
 * Evaluations — saro-data-framework run history + trigger.
 *
 * STORY-009: AI Auditor (and admin/super_admin) can trigger a new evaluation
 * batch job directly from this screen.
 *
 * POST /api/v1/evaluations/trigger  — fire a background eval run
 * GET  /api/v1/evaluations          — list past runs
 */
import React, { useEffect, useState } from "react";

const AVAILABLE_DATASETS = [
  { id: "real_toxicity_prompts", label: "Real Toxicity Prompts" },
  { id: "guardrails_hallucination", label: "Guardrails Hallucination" },
  { id: "pii_masking",            label: "PII Masking" },
  { id: "crows_pairs",            label: "CrowS-Pairs (Bias)" },
  { id: "truthfulqa",             label: "TruthfulQA" },
];

const STATUS_STYLE = {
  completed: { bg: "#d1fae5", color: "#065f46" },
  running:   { bg: "#dbeafe", color: "#1d4ed8" },
  failed:    { bg: "#fee2e2", color: "#991b1b" },
  pending:   { bg: "#f3f4f6", color: "#6b7280" },
};

export default function Evaluations({ token, user }) {
  const persona = user?.persona_role || user?.role || "operator";
  const canTrigger = ["ai_auditor", "admin", "super_admin"].includes(persona);

  const [evals, setEvals]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  // Trigger form state
  const [showTrigger, setShowTrigger]     = useState(false);
  const [selectedDS, setSelectedDS]       = useState([]);
  const [maxSamples, setMaxSamples]       = useState(200);
  const [triggering, setTriggering]       = useState(false);
  const [triggerError, setTriggerError]   = useState(null);
  const [triggerSuccess, setTriggerSuccess] = useState(null);

  function loadEvals() {
    if (!token) return;
    setLoading(true);
    fetch("/api/v1/evaluations", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setEvals(Array.isArray(d) ? d : d.items || []); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }

  useEffect(loadEvals, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggleDataset(id) {
    setSelectedDS((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  }

  async function triggerRun() {
    setTriggering(true);
    setTriggerError(null);
    setTriggerSuccess(null);
    try {
      const body = {
        datasets: selectedDS.length > 0 ? selectedDS : null, // null = all
        max_samples: maxSamples,
      };
      const r = await fetch("/api/v1/evaluations/trigger", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.status }));
        throw new Error(err.detail || `${r.status}`);
      }
      const result = await r.json();
      setTriggerSuccess(`Evaluation run started — ID: ${(result.id || result.run_id || "").toString().slice(0, 8)}…`);
      setShowTrigger(false);
      setSelectedDS([]);
      // Reload list after a brief delay so the new run appears
      setTimeout(loadEvals, 1500);
    } catch (e) {
      setTriggerError(e.message);
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, marginBottom: 4 }}>🧪 Evaluations</h1>
          <p style={{ color: "#6b7280", fontSize: 14, margin: 0 }}>
            Batch evaluation run history — TruthfulQA, PII detection, toxicity analysis.
          </p>
        </div>
        {canTrigger && (
          <button
            onClick={() => { setShowTrigger((v) => !v); setTriggerError(null); setTriggerSuccess(null); }}
            style={{
              padding: "9px 18px", background: "#0d9488", color: "#fff",
              border: "none", borderRadius: 8, cursor: "pointer", fontSize: 14, fontWeight: 600,
            }}
          >
            {showTrigger ? "Cancel" : "+ Trigger Eval Run"}
          </button>
        )}
      </div>

      {/* Trigger form */}
      {showTrigger && canTrigger && (
        <div style={{
          background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10,
          padding: 20, marginBottom: 20,
        }}>
          <h2 style={{ fontSize: 15, marginBottom: 12, color: "#065f46" }}>Configure Evaluation Run</h2>

          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>
              Datasets <span style={{ fontWeight: 400, color: "#9ca3af" }}>(leave all unchecked to run all)</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {AVAILABLE_DATASETS.map((ds) => {
                const checked = selectedDS.includes(ds.id);
                return (
                  <label
                    key={ds.id}
                    style={{
                      display: "flex", alignItems: "center", gap: 6,
                      padding: "6px 12px", borderRadius: 6, cursor: "pointer",
                      border: `1px solid ${checked ? "#0d9488" : "#d1d5db"}`,
                      background: checked ? "#ccfbf1" : "#fff",
                      fontSize: 13, fontWeight: checked ? 600 : 400,
                      color: checked ? "#0f766e" : "#374151",
                      userSelect: "none",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleDataset(ds.id)}
                      style={{ display: "none" }}
                    />
                    {checked ? "✓ " : ""}{ds.label}
                  </label>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: "#374151" }}>
              Max samples per dataset:
            </label>
            <input
              type="number"
              min={50}
              max={2000}
              step={50}
              value={maxSamples}
              onChange={(e) => setMaxSamples(Number(e.target.value))}
              style={{ width: 90, padding: "6px 8px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}
            />
            <span style={{ fontSize: 12, color: "#9ca3af" }}>50–2 000 samples</span>
          </div>

          {triggerError && (
            <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 6, padding: "8px 12px", color: "#b91c1c", fontSize: 13, marginBottom: 12 }}>
              ⚠ {triggerError}
            </div>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={triggerRun}
              disabled={triggering}
              style={{
                padding: "8px 20px", background: triggering ? "#9ca3af" : "#0d9488", color: "#fff",
                border: "none", borderRadius: 7, cursor: triggering ? "default" : "pointer",
                fontSize: 14, fontWeight: 600,
              }}
            >
              {triggering ? "Starting…" : "▶ Start Run"}
            </button>
            <button
              onClick={() => setShowTrigger(false)}
              style={{
                padding: "8px 16px", background: "transparent", color: "#6b7280",
                border: "1px solid #d1d5db", borderRadius: 7, cursor: "pointer", fontSize: 14,
              }}
            >
              Cancel
            </button>
          </div>

          <p style={{ fontSize: 11, color: "#6b7280", marginTop: 10, margin: "10px 0 0" }}>
            Evaluation runs execute in the background. Results will appear in the list below when complete.
            Human review required before acting on any evaluation finding.
          </p>
        </div>
      )}

      {/* Success toast */}
      {triggerSuccess && (
        <div style={{ background: "#d1fae5", border: "1px solid #6ee7b7", borderRadius: 8, padding: "10px 14px", color: "#065f46", fontSize: 13, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
          ✓ {triggerSuccess}
          <button onClick={() => setTriggerSuccess(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280", marginLeft: "auto", fontSize: 16 }}>×</button>
        </div>
      )}

      {loading && <div style={{ color: "#9ca3af" }}>Loading evaluations…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13, marginBottom: 16 }}>
          ⚠ {error}
        </div>
      )}
      {!loading && !error && evals.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          {canTrigger
            ? 'No evaluation runs yet. Use "+ Trigger Eval Run" above to start one.'
            : "No evaluation runs yet."}
        </div>
      )}

      {evals.map((ev) => {
        const st = STATUS_STYLE[(ev.status || "").toLowerCase()] || STATUS_STYLE.pending;
        const passed = ev.datasets_passed ?? null;
        const total  = ev.datasets_attempted ?? null;
        return (
          <div key={ev.id || ev.run_id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{ev.name || ev.eval_type || "Evaluation Run"}</span>
                  <span style={{ background: st.bg, color: st.color, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    {ev.status}
                  </span>
                  {passed !== null && total !== null && (
                    <span style={{ fontSize: 12, color: "#6b7280" }}>
                      {passed}/{total} datasets passed
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 20, fontSize: 12, color: "#9ca3af", flexWrap: "wrap" }}>
                  {ev.eval_type && <span>Type: {ev.eval_type}</span>}
                  {ev.sample_count != null && <span>Samples: {ev.sample_count}</span>}
                  {ev.total_samples_uploaded != null && <span>Uploaded: {ev.total_samples_uploaded.toLocaleString()}</span>}
                  {ev.elapsed_seconds != null && <span>Duration: {ev.elapsed_seconds.toFixed(1)}s</span>}
                  {ev.created_at && <span>Started: {ev.created_at.slice(0, 16).replace("T", " ")}</span>}
                  {ev.completed_at && <span>Completed: {ev.completed_at.slice(0, 16).replace("T", " ")}</span>}
                </div>
                {ev.error_message && (
                  <div style={{ marginTop: 8, fontSize: 12, color: "#b91c1c", background: "#fee2e2", padding: "6px 10px", borderRadius: 5 }}>
                    {ev.error_message}
                  </div>
                )}
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
