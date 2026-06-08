/**
 * TRACE View — load any audit ID and display 6-step pipeline timeline.
 * Executive / Technical toggle, full chain-of-thought.
 */
import React, { useState } from "react";

const STEPS = [
  { key: "ingest",    label: "1. Ingest" },
  { key: "classify",  label: "2. Classify" },
  { key: "match",     label: "3. Match" },
  { key: "score",     label: "4. Score" },
  { key: "explain",   label: "5. Explain" },
  { key: "remediate", label: "6. Remediate" },
];

const STATUS_STYLES = {
  done:    { bg: "#d1fae5", color: "#065f46", icon: "✓" },
  pass:    { bg: "#d1fae5", color: "#065f46", icon: "✓" },
  warn:    { bg: "#fef3c7", color: "#92400e", icon: "⚠" },
  fail:    { bg: "#fee2e2", color: "#991b1b", icon: "✗" },
  pending: { bg: "#f3f4f6", color: "#6b7280", icon: "…" },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending;
  return (
    <span style={{ background: s.bg, color: s.color, padding: "2px 8px", borderRadius: 4, fontSize: 12, fontWeight: 700 }}>
      {s.icon} {(status || "pending").toUpperCase()}
    </span>
  );
}

function RiskChip({ score }) {
  if (score == null) return null;
  const s = Math.round(score * 100);
  const color = s >= 70 ? "#dc2626" : s >= 40 ? "#ca8a04" : "#16a34a";
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, padding: "2px 10px", borderRadius: 12, fontWeight: 700, fontSize: 14 }}>
      {s}/100
    </span>
  );
}

export default function TraceView({ token }) {
  const [auditId, setAuditId] = useState("");
  const [trace, setTrace]     = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [mode, setMode]       = useState("summary"); // summary | technical

  async function load() {
    if (!auditId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`/api/v1/traces/${auditId.trim()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`${r.status} — audit not found`);
      setTrace(await r.json());
    } catch (e) {
      setError(e.message);
      setTrace(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🔍 TRACE View</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Enter an Audit ID to view its 6-step TRACE pipeline timeline.
      </p>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          value={auditId}
          onChange={(e) => setAuditId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          placeholder="Audit ID (UUID)…"
          style={{ flex: 1, padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14 }}
        />
        <button
          onClick={load}
          disabled={loading}
          style={{ padding: "10px 20px", background: "#0d9488", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 14 }}
        >
          {loading ? "Loading…" : "Load TRACE"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 14px", color: "#b91c1c", fontSize: 13, marginBottom: 16 }}>
          ⚠ {error}
        </div>
      )}

      {trace && (
        <>
          {/* Header */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div style={{ fontFamily: "monospace", fontSize: 13, color: "#6b7280" }}>
                {(trace.audit_id || auditId).slice(0, 16)}…
              </div>
              <StatusBadge status={trace.status} />
              <RiskChip score={trace.risk_score} />
              <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                {["summary", "technical"].map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    style={{
                      padding: "4px 12px", borderRadius: 20, fontSize: 12,
                      background: mode === m ? "#0d9488" : "#f3f4f6",
                      color: mode === m ? "#fff" : "#374151",
                      border: "none", cursor: "pointer",
                    }}
                  >
                    {m.charAt(0).toUpperCase() + m.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Pipeline timeline */}
          <div style={{ display: "flex", gap: 8, marginBottom: 20, overflowX: "auto", paddingBottom: 4 }}>
            {STEPS.map((step, i) => {
              const stepData = trace.steps?.[step.key] || trace[step.key] || {};
              const status = stepData.status || (i < (trace.steps_completed || 6) ? "done" : "pending");
              const ss = STATUS_STYLES[status] || STATUS_STYLES.pending;
              return (
                <React.Fragment key={step.key}>
                  <div style={{
                    padding: "10px 14px", borderRadius: 8, background: ss.bg, color: ss.color,
                    minWidth: 100, textAlign: "center", border: `1px solid ${ss.color}30`,
                  }}>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{step.label}</div>
                    <div style={{ fontSize: 11, marginTop: 2 }}>{ss.icon} {status}</div>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div style={{ color: "#9ca3af", fontSize: 18, display: "flex", alignItems: "center" }}>→</div>
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {/* Detail panels */}
          {STEPS.map((step) => {
            const stepData = trace.steps?.[step.key] || trace[step.key];
            if (!stepData) return null;
            return (
              <div key={step.key} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{step.label}</span>
                  <StatusBadge status={stepData.status} />
                  {stepData.confidence_score != null && (
                    <span style={{ fontSize: 12, color: "#6b7280" }}>
                      Confidence: {(stepData.confidence_score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {mode === "summary" && stepData.summary && (
                  <p style={{ fontSize: 13, color: "#374151", margin: 0 }}>{stepData.summary}</p>
                )}
                {mode === "technical" && (
                  <pre style={{ fontSize: 11, background: "#f8fafc", padding: 10, borderRadius: 6, overflow: "auto", margin: 0 }}>
                    {JSON.stringify(stepData, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}

          {/* Hash chain */}
          {trace.hash_chain_valid != null && (
            <div style={{
              padding: "10px 14px", borderRadius: 8, marginTop: 8,
              background: trace.hash_chain_valid ? "#d1fae5" : "#fee2e2",
              border: `1px solid ${trace.hash_chain_valid ? "#6ee7b7" : "#fca5a5"}`,
              fontSize: 13, color: trace.hash_chain_valid ? "#065f46" : "#991b1b",
            }}>
              {trace.hash_chain_valid ? "✓" : "✗"} Hash chain integrity: {trace.hash_chain_valid ? "verified" : "BROKEN"} — TRACE chain integrity verifiable via SHA-256 hash chain — evidence for human auditor review.
            </div>
          )}
        </>
      )}
    </div>
  );
}
