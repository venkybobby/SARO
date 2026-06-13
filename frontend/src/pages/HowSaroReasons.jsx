/**
 * How SARO Reasons — explains the 4-gate pipeline and SHAP-based scoring logic.
 */
import React from "react";

const GATES = [
  {
    id: "G1", name: "Gate 1 — Batch Validation",
    desc: "Validates input meets statistical requirements (min 50 samples per internal heuristic). Checks data quality and completeness before scoring begins.",
    note: "The 50-sample minimum is an internal statistical heuristic, not a regulatory requirement.",
  },
  {
    id: "G2", name: "Gate 2 — Fairness Analysis",
    desc: "Computes statistical parity and disparity metrics across protected attributes. Uses Fisher's exact test for group fairness detection.",
    note: "Evidence supporting NIST AI RMF Measure 2.5 — human review required.",
  },
  {
    id: "G3", name: "Gate 3 — Drift Detection",
    desc: "Runs Kolmogorov-Smirnov (KS) test against baseline distributions. Triggers circuit breaker at 2σ deviation threshold.",
    note: "Auto-incident is created when drift exceeds 2σ. Human must review and clear.",
  },
  {
    id: "G4", name: "Gate 4 — Compliance Mapping",
    desc: "Maps scoring findings to framework controls: NIST AI RMF, EU AI Act, ISO 42001, AIGP. Generates TRACE timeline evidence package.",
    note: "Evidence for human auditor review — SARO does not certify compliance.",
  },
];

const DIR_FORMULA = "DIR = (Σ gate_weights × gate_scores) / Σ gate_weights";

export default function HowSaroReasons() {
  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 900 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>💡 How SARO Reasons</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 24 }}>
        SARO uses a 4-gate pipeline with SHAP-based explainability to compute a 0–100 risk score from AI prompt + output pairs.
        Core scoring never calls external AI models — it only accepts <code>prompt</code> + <code>raw_output</code>. An optional Gate-3 verification pass calls a configured LLM only if you enable it (off by default).
      </p>

      {/* DIR Formula */}
      <div style={{ background: "#0f172a", color: "#e2e8f0", borderRadius: 8, padding: 20, marginBottom: 24, fontFamily: "monospace" }}>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          DIR Formula (Decision Integrated Risk Score)
        </div>
        <div style={{ fontSize: 16, color: "#0d9488" }}>{DIR_FORMULA}</div>
        <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
          Output: integer 0–100 · 0 = lowest risk · 100 = highest risk
        </div>
      </div>

      {/* Gates */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 16 }}>4-Gate Pipeline</h2>
        {GATES.map((gate, i) => (
          <div key={gate.id} style={{ display: "flex", gap: 16, marginBottom: 16 }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#0d9488", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13, flexShrink: 0 }}>
              {i + 1}
            </div>
            <div style={{ flex: 1, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>{gate.name}</div>
              <p style={{ fontSize: 13, color: "#374151", margin: "0 0 8px" }}>{gate.desc}</p>
              <div style={{ fontSize: 11, color: "#9ca3af", fontStyle: "italic" }}>{gate.note}</div>
            </div>
          </div>
        ))}
      </div>

      {/* SHAP */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 8 }}>SHAP Explainability</h2>
        <p style={{ fontSize: 13, color: "#374151", margin: 0 }}>
          SARO uses SHAP (SHapley Additive exPlanations) values to decompose each risk score into contributions from individual features —
          tone, semantic similarity, policy violations, drift deviation, and framework gap flags.
          This provides human-readable explanations for every score, supporting the HITL (Human-In-The-Loop) review workflow.
        </p>
      </div>

      {/* Non-negotiables */}
      <div style={{ background: "#fef3c7", border: "1px solid #fde68a", borderRadius: 8, padding: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 8, color: "#92400e" }}>SARO Non-Negotiables</h3>
        <ul style={{ margin: 0, padding: "0 0 0 20px", fontSize: 13, color: "#374151" }}>
          <li>Accepts only <code>prompt</code> + <code>raw_output</code> — core scoring never calls external AI models (optional Gate-3 judge off by default)</li>
          <li>Returns only risk score (0–100), TRACE timeline, and remediation guidance</li>
          <li>Never writes to client systems</li>
          <li>Never certifies compliance — evidence support only</li>
          <li>Human-in-the-loop always — AIGP human certification, not automated sign-off</li>
          <li>Read-only integration posture across all connectors</li>
        </ul>
      </div>
    </div>
  );
}
