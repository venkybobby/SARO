/**
 * Compliance Hub — landing page for compliance_lead persona.
 * Sections: EVF Validation Status, Recent Audits, Governance Docs, QCO Expiry Alerts, Readiness Checklist.
 */
import React, { useEffect, useState } from "react";

const TIER_CONFIG = {
  tier_1: { color: "#16a34a", icon: "✅", short: "EXTERNALLY REVIEWED" },
  tier_2: { color: "#ca8a04", icon: "⏳", short: "UNDER REVIEW" },
  tier_3: { color: "#64748b", icon: "🔒", short: "INTERNAL ONLY" },
};

const CHECKLIST = [
  "Data processing agreements in place",
  "AI systems registered in inventory",
  "Risk assessments completed for high-risk systems",
  "Human oversight controls documented",
  "Incident response plan reviewed",
  "Annual compliance review scheduled",
];

function api(token, path) {
  return fetch(path, { headers: { Authorization: `Bearer ${token}` } }).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  });
}

function Card({ children, style }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, ...style }}>
      {children}
    </div>
  );
}

function TierBadge({ tier, label, qcoRef }) {
  const cfg = TIER_CONFIG[tier] || { color: "#64748b", icon: "?", short: "UNKNOWN" };
  return (
    <span
      style={{
        background: cfg.color + "20", color: cfg.color,
        border: `1px solid ${cfg.color}40`,
        padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700,
      }}
      title={label || ""}
    >
      {cfg.icon} {cfg.short}{qcoRef ? ` · ${qcoRef}` : ""}
    </span>
  );
}

function RiskBadge({ score }) {
  const s = score * 100;
  const color = s >= 70 ? "#dc2626" : s >= 40 ? "#ca8a04" : "#16a34a";
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
      {s.toFixed(0)}
    </span>
  );
}

export default function ComplianceHub({ token, tenantId }) {
  const [coverage, setCoverage] = useState(null);
  const [audits, setAudits] = useState([]);
  const [checks, setChecks] = useState(CHECKLIST.map(() => false));
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    api(token, `/api/v1/compliance-matrix/coverage?tenant_id=${tenantId}&window=30d`)
      .then(setCoverage)
      .catch(() => setError("Coverage data unavailable"));
    api(token, `/api/v1/audits?tenant_id=${tenantId}&limit=10&sort=desc`)
      .then((d) => setAudits(Array.isArray(d) ? d : d.items || []))
      .catch(() => {});
  }, [token, tenantId]);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1200 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🏛️ Compliance Hub</h1>
      <p style={{ color: "#6b7280", marginBottom: 24, fontSize: 14 }}>
        EVF validation status, recent audits, and readiness tracking for compliance leads.
      </p>

      {/* EVF Validation Status */}
      <Card style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 16 }}>EVF Validation Status</h2>
        {error && <div style={{ color: "#dc2626", marginBottom: 12, fontSize: 13 }}>⚠ {error}</div>}
        {coverage?.frameworks ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {coverage.frameworks.map((fw) => (
              <div key={fw.name} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{fw.name}</span>
                  <span style={{ fontSize: 13, color: "#0d9488" }}>{fw.coverage_pct?.toFixed(1)}%</span>
                </div>
                <div style={{ height: 4, background: "#e5e7eb", borderRadius: 2, marginBottom: 8 }}>
                  <div style={{ height: 4, width: `${fw.coverage_pct || 0}%`, background: "#0d9488", borderRadius: 2 }} />
                </div>
                {fw.evf_tier && (
                  <TierBadge tier={fw.evf_tier} label={fw.evf_label} qcoRef={fw.evf_qco_reference} />
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading EVF validation data…</div>
        )}
      </Card>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        {/* Recent Audits */}
        <Card style={{ flex: 2, minWidth: 300 }}>
          <h2 style={{ fontSize: 15, marginBottom: 12 }}>Recent Audits</h2>
          {audits.length === 0 ? (
            <div style={{ color: "#9ca3af", fontSize: 13 }}>No audits yet.</div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                  <th style={{ textAlign: "left", padding: "6px 8px", color: "#6b7280", fontWeight: 600 }}>Audit ID</th>
                  <th style={{ textAlign: "left", padding: "6px 8px", color: "#6b7280", fontWeight: 600 }}>Status</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", color: "#6b7280", fontWeight: 600 }}>Risk Score</th>
                </tr>
              </thead>
              <tbody>
                {audits.slice(0, 10).map((a) => (
                  <tr key={a.audit_id || a.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "8px 8px", fontFamily: "monospace", fontSize: 11 }}>
                      {(a.audit_id || a.id || "").slice(0, 12)}…
                    </td>
                    <td style={{ padding: "8px 8px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 10, fontSize: 11,
                        background: a.status === "completed" ? "#d1fae5" : a.status === "failed" ? "#fee2e2" : "#fef3c7",
                        color: a.status === "completed" ? "#065f46" : a.status === "failed" ? "#991b1b" : "#92400e",
                      }}>{a.status}</span>
                    </td>
                    <td style={{ padding: "8px 8px", textAlign: "right" }}>
                      {a.risk_score != null ? <RiskBadge score={a.risk_score} /> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {/* Readiness Checklist */}
        <Card style={{ flex: 1, minWidth: 240 }}>
          <h2 style={{ fontSize: 15, marginBottom: 12 }}>Readiness Checklist</h2>
          <div style={{ fontSize: 13 }}>
            {CHECKLIST.map((item, i) => (
              <label key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={checks[i]}
                  onChange={() => setChecks((c) => { const n = [...c]; n[i] = !n[i]; return n; })}
                  style={{ marginTop: 2, accentColor: "#0d9488" }}
                />
                <span style={{ color: checks[i] ? "#9ca3af" : "#374151", textDecoration: checks[i] ? "line-through" : "none" }}>
                  {item}
                </span>
              </label>
            ))}
            <div style={{ marginTop: 12, color: "#0d9488", fontWeight: 600, fontSize: 13 }}>
              {checks.filter(Boolean).length}/{CHECKLIST.length} complete
            </div>
          </div>
        </Card>
      </div>

      {/* Disclaimer */}
      <div style={{ marginTop: 24, padding: 12, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: 11, color: "#64748b" }}>
        <strong>Disclaimer:</strong> This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification, legal advice, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission.
      </div>
    </div>
  );
}
