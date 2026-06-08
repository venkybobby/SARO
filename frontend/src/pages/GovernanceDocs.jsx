/**
 * Governance Docs — DPA, sub-processors, retention policy, IR Plan links.
 */
import React, { useEffect, useState } from "react";

const DOC_LINKS = [
  { label: "DPA Template",        key: "dpa_template",    icon: "📄" },
  { label: "Sub-Processors List", key: "sub_processors",  icon: "🔗" },
  { label: "Retention Policy",    key: "retention_policy",icon: "🗂️" },
];

export default function GovernanceDocs({ token }) {
  const [docs, setDocs]     = useState({});
  const [irPlan, setIrPlan] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    const h = { Authorization: `Bearer ${token}` };

    fetch("/api/v1/governance/docs", { headers: h })
      .then((r) => r.ok ? r.json() : {})
      .then(setDocs)
      .catch(() => {})
      .finally(() => setLoading(false));

    fetch("/api/v1/governance/ir-plan", { headers: h })
      .then((r) => r.ok ? r.json() : null)
      .then(setIrPlan)
      .catch(() => {});
  }, [token]);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 900 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📄 DPA & Governance</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Data processing agreements, sub-processor lists, retention policies, and incident response plan.
      </p>

      {/* Governance documents */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 12 }}>Governance Documents</h2>
        {loading ? (
          <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading…</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
            {DOC_LINKS.map((doc) => {
              const url = docs[doc.key];
              return (
                <div
                  key={doc.key}
                  style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, display: "flex", alignItems: "center", gap: 10 }}
                >
                  <span style={{ fontSize: 20 }}>{doc.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{doc.label}</div>
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: "#0d9488" }}>
                        Download ↗
                      </a>
                    ) : (
                      <span style={{ fontSize: 12, color: "#9ca3af" }}>Not available</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* IR Plan */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 12 }}>🚨 Incident Response Plan</h2>
        {irPlan ? (
          <div>
            {irPlan.phases?.map((phase, i) => (
              <div key={i} style={{ marginBottom: 16 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: "#0d9488", marginBottom: 6 }}>
                  Phase {i + 1}: {phase.name}
                </div>
                <p style={{ fontSize: 13, color: "#374151", margin: "0 0 6px" }}>{phase.description}</p>
                {phase.steps?.length > 0 && (
                  <ol style={{ margin: 0, padding: "0 0 0 20px", fontSize: 13, color: "#374151" }}>
                    {phase.steps.map((step, j) => <li key={j} style={{ marginBottom: 4 }}>{step}</li>)}
                  </ol>
                )}
              </div>
            ))}
            {!irPlan.phases && (
              <pre style={{ fontSize: 12, background: "#f8fafc", padding: 12, borderRadius: 6, overflow: "auto" }}>
                {JSON.stringify(irPlan, null, 2)}
              </pre>
            )}
          </div>
        ) : (
          <div style={{ color: "#9ca3af", fontSize: 13 }}>Incident response plan not configured. Contact your administrator.</div>
        )}
      </div>
    </div>
  );
}
