/**
 * Governance Trust — trust documents and AI governance framework reference (CF-05).
 */
import React, { useEffect, useState } from "react";

export default function Governance({ token }) {
  const [docs, setDocs]     = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/governance/trust-documents", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then((d) => { setDocs(Array.isArray(d) ? d : d.documents || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  const PRINCIPLES = [
    { icon: "🔍", title: "Transparency", desc: "SARO produces human-readable TRACE timelines and SHAP explanations for every risk score." },
    { icon: "👤", title: "Human Oversight", desc: "Every SARO output requires human review before any compliance action. Automated sign-off is never permitted." },
    { icon: "⚖️", title: "Accountability", desc: "Immutable SHA-256 hash-chained audit trails maintain a verifiable record of all risk assessments." },
    { icon: "🔒", title: "Privacy by Design", desc: "SARO never stores raw prompt content beyond the session. Only anonymised metrics and evidence records are retained." },
    { icon: "📋", title: "Evidence-Based", desc: "All framework mappings (NIST, EU AI Act, ISO 42001, AIGP) are evidence for auditors — not compliance certifications." },
  ];

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🏛️ Governance Trust</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 24 }}>
        SARO AI governance framework principles, trust documents, and accountability structure.
      </p>

      {/* Principles */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, marginBottom: 12 }}>AI Governance Principles</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
          {PRINCIPLES.map((p) => (
            <div key={p.title} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 20, marginBottom: 6 }}>{p.icon}</div>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>{p.title}</div>
              <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>{p.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Trust documents */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 12 }}>Trust Documents</h2>
        {loading && <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading…</div>}
        {!loading && docs.length === 0 && (
          <div style={{ color: "#9ca3af", fontSize: 13 }}>No trust documents configured. Contact your administrator.</div>
        )}
        {docs.map((doc, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: "1px solid #f3f4f6" }}>
            <span style={{ fontSize: 16 }}>📄</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{doc.title || doc.name}</div>
              {doc.description && <div style={{ fontSize: 11, color: "#9ca3af" }}>{doc.description}</div>}
            </div>
            {doc.url && (
              <a href={doc.url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 12, color: "#0d9488", textDecoration: "none" }}>
                View ↗
              </a>
            )}
          </div>
        ))}
      </div>

      <div style={{ marginTop: 20, padding: 12, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: 11, color: "#64748b" }}>
        SARO provides audit evidence for ISO 42001 document lifecycle review. It does not certify management systems or conduct Stage 1/Stage 2 audits.
      </div>
    </div>
  );
}
