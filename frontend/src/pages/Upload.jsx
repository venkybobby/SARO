/**
 * Upload & Scan — submit AI output for risk scanning via POST /api/v1/scan.
 */
import React, { useState } from "react";

const SOURCE_MODELS = ["openai", "claude", "grok", "sierra", "internal", "unknown"];
const VERTICALS = ["finance", "healthcare", "legal", "government", "general"];

export default function Upload({ token, tenantId }) {
  const [prompt, setPrompt]     = useState("");
  const [output, setOutput]     = useState("");
  const [model, setModel]       = useState("openai");
  const [vertical, setVertical] = useState("finance");
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/v1/scan", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          raw_output: output,
          source_model: model,
          vertical,
          tenant_id: tenantId,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `Scan failed (${r.status})`);
      }
      setResult(await r.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const riskScore = result?.risk_score != null ? Math.round(result.risk_score * 100) : null;
  const riskColor = riskScore >= 70 ? "#dc2626" : riskScore >= 40 ? "#ca8a04" : "#16a34a";

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 900 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📤 Upload & Scan</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Submit an AI prompt + output for SARO risk scoring. SARO accepts only <code>prompt</code> + <code>raw_output</code> — it never calls external AI models.
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Source Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                {SOURCE_MODELS.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Vertical</label>
              <select
                value={vertical}
                onChange={(e) => setVertical(e.target.value)}
                style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
              >
                {VERTICALS.map((v) => <option key={v}>{v}</option>)}
              </select>
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              Prompt <span style={{ color: "#9ca3af" }}>(what the user sent to the AI)</span>
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              required
              rows={4}
              placeholder="Enter the original prompt…"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13, resize: "vertical", boxSizing: "border-box" }}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              Raw Output <span style={{ color: "#9ca3af" }}>(the AI's response)</span>
            </label>
            <textarea
              value={output}
              onChange={(e) => setOutput(e.target.value)}
              required
              rows={6}
              placeholder="Paste the AI model's output here…"
              style={{ width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13, resize: "vertical", boxSizing: "border-box" }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{ padding: "10px 24px", background: loading ? "#99f6e4" : "#0d9488", color: "#fff", border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer" }}
          >
            {loading ? "Scanning…" : "Run SARO Scan →"}
          </button>
        </div>
      </form>

      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13, marginBottom: 16 }}>
          ⚠ {error}
        </div>
      )}

      {result && (
        <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontSize: 16, marginBottom: 16 }}>Scan Result</h2>

          <div style={{ display: "flex", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
            <div style={{ padding: 16, background: riskColor + "10", border: `1px solid ${riskColor}30`, borderRadius: 8, textAlign: "center", minWidth: 120 }}>
              <div style={{ fontSize: 36, fontWeight: 800, color: riskColor }}>{riskScore}</div>
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>Risk Score /100</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>
                SARO scored this output at {riskScore}/100 — <span style={{ color: riskColor }}>{riskScore >= 70 ? "HIGH RISK" : riskScore >= 40 ? "MODERATE RISK" : "LOW RISK"}</span>
              </div>
              {result.audit_id && (
                <div style={{ fontSize: 12, color: "#9ca3af", fontFamily: "monospace" }}>
                  Audit ID: {result.audit_id}
                </div>
              )}
            </div>
          </div>

          {result.remediation_guidance && (
            <div style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, color: "#374151", marginBottom: 8 }}>Recommended Remediation</h3>
              <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: 12, fontSize: 13, color: "#374151" }}>
                {result.remediation_guidance}
              </div>
              <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>Recommended remediation — human validation required</div>
            </div>
          )}

          {result.findings?.length > 0 && (
            <div>
              <h3 style={{ fontSize: 14, color: "#374151", marginBottom: 8 }}>Findings</h3>
              {result.findings.map((f, i) => {
                const color = f.result === "fail" || f.result === "flagged" ? "#dc2626" : f.result === "warn" ? "#ca8a04" : "#16a34a";
                return (
                  <div key={i} style={{ padding: "10px 12px", border: "1px solid #e5e7eb", borderRadius: 6, marginBottom: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ background: color + "20", color, padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>
                        {(f.result || "info").toUpperCase()}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{f.rule_id || f.name || `Finding ${i + 1}`}</span>
                    </div>
                    {f.message && <p style={{ margin: "6px 0 0", fontSize: 13, color: "#4b5563" }}>{f.message}</p>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
