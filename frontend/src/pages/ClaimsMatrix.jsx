/**
 * Claims Matrix — SARO Compliance Claims Matrix, framework boundary details, EVF status.
 */
import React, { useEffect, useState } from "react";

const MATRIX_ROWS = [
  { scenario: "Risk assessment", does: "Computes 0–100 risk score from prompt + output", doesNot: 'Determine if AI system is "safe" or "compliant"', language: '"SARO scored this output at {score}/100"' },
  { scenario: "NIST AI RMF",     does: "Maps findings to RMF function areas (Govern, Map, Measure, Manage)", doesNot: "Assert RMF conformance", language: '"Evidence supporting NIST AI RMF Measure 2.5"' },
  { scenario: "EU AI Act",       does: "Identifies characteristics associated with high-risk system categories", doesNot: "Classify a system as high-risk under EU law", language: '"Indicators consistent with EU AI Act high-risk criteria"' },
  { scenario: "ISO 42001",       does: "Links scan records to document lifecycle stages", doesNot: "Issue ISO 42001 certificates", language: '"Audit evidence for ISO 42001 document lifecycle review"' },
  { scenario: "AIGP",            does: "Supports human reviewer workflows", doesNot: "Auto-certify under AIGP", language: '"Evidence package for AIGP-certified human reviewer"' },
  { scenario: "Audit trail",     does: "Generates immutable TRACE timelines", doesNot: "Guarantee audit admissibility", language: '"TRACE record for human auditor review"' },
  { scenario: "Hash chain",      does: "Computes SHA-256 hash-chained audit traces", doesNot: "Guarantee tamper-proof storage or certify chain of custody", language: '"TRACE chain integrity verifiable via SHA-256 hash chain"' },
  { scenario: "Remediation",     does: "Provides guidance text", doesNot: "Guarantee remediation effectiveness", language: '"Recommended remediation — human validation required"' },
  { scenario: "Certification",   does: "Provides evidence packages", doesNot: "Issue, sign, or endorse certificates", language: '"Supporting evidence — certification requires human authority"' },
];

const EVF_STATUS = [
  { framework: "EU AI Act",      scope: "Arts. 9, 13, 17 evidence support only", status: "Internal Review Only", tier: "tier_3" },
  { framework: "NIST AI RMF 1.0",scope: "Govern, Map, Measure subcategory coverage", status: "Internal Review Only", tier: "tier_3" },
  { framework: "AIGP",           scope: "Principles evaluation framework only", status: "Internal Review Only", tier: "tier_3" },
  { framework: "ISO 42001",      scope: "Document lifecycle linking and control objective support", status: "Internal Review Only", tier: "tier_3" },
];

export default function ClaimsMatrix({ token }) {
  const [liveData, setLiveData] = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/compliance-matrix/summary", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setLiveData(d); })
      .catch(() => {});
  }, [token]);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1100 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📋 Claims Matrix</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Defines the precise boundary between what SARO claims to do and what it explicitly does not claim.
        All compliance-related code, docs, and UI copy must conform to this matrix.
      </p>

      {/* Decision Matrix */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 20, overflow: "auto" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb", fontWeight: 700, fontSize: 14 }}>
          Decision Matrix
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Scenario</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#059669", borderBottom: "1px solid #e5e7eb" }}>SARO Does</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#dc2626", borderBottom: "1px solid #e5e7eb" }}>SARO Does NOT Do</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>Approved Language</th>
            </tr>
          </thead>
          <tbody>
            {MATRIX_ROWS.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "10px 12px", fontWeight: 600 }}>{row.scenario}</td>
                <td style={{ padding: "10px 12px", color: "#059669" }}>{row.does}</td>
                <td style={{ padding: "10px 12px", color: "#dc2626" }}>{row.doesNot}</td>
                <td style={{ padding: "10px 12px", fontFamily: "monospace", color: "#6b7280", fontSize: 11 }}>{row.language}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* EVF Validation Status */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 20, overflow: "auto" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb", fontWeight: 700, fontSize: 14 }}>
          EVF Validation Status (SARO-RISK-001)
        </div>
        <div style={{ padding: "10px 16px", background: "#fffbeb", borderBottom: "1px solid #fde68a", fontSize: 12, color: "#92400e" }}>
          ⚠ No framework claim has completed External SME Validation (EVF). All four frameworks are in <strong>Internal Review Only</strong> state. No external compliance claim may be made until a QCO is issued.
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Framework</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Locked Claim Scope</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>EVF Status</th>
            </tr>
          </thead>
          <tbody>
            {EVF_STATUS.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "10px 12px", fontWeight: 600 }}>{row.framework}</td>
                <td style={{ padding: "10px 12px", color: "#6b7280" }}>{row.scope}</td>
                <td style={{ padding: "10px 12px" }}>
                  <span style={{ background: "#f1f5f9", color: "#64748b", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    🔒 {row.status} — Not for External Claim
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Required Disclaimer */}
      <div style={{ padding: 14, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12, color: "#64748b", fontStyle: "italic" }}>
        <strong>Required Disclaimer (all reports):</strong> This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification, legal advice, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission.
      </div>
    </div>
  );
}
