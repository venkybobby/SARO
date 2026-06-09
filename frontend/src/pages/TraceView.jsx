import React, { useEffect, useState } from "react";

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

export default function TraceView({ token, initialAuditId }) {
  const [auditId, setAuditId]   = useState(initialAuditId || "");
  const [trace, setTrace]       = useState(null);
  const [auditMeta, setAuditMeta] = useState(null); // rule_pack_hash + created_at from audit report
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [mode, setMode]         = useState("summary");
  const [recent, setRecent]     = useState([]);
  const [recentLoading, setRecentLoading] = useState(true);

  useEffect(() => {
    async function loadRecent() {
      setRecentLoading(true);
      try {
        const r = await fetch("/api/v1/audits?limit=10&sort=desc", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) setRecent(await r.json());
      } catch {
        // non-fatal — recent list is a convenience feature
      } finally {
        setRecentLoading(false);
      }
    }
    loadRecent();
  }, [token]);

  useEffect(() => {
    if (initialAuditId) load(initialAuditId);
  }, [initialAuditId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function load(id) {
    const target = (id || auditId).trim();
    if (!target) return;
    if (id) setAuditId(id);
    setLoading(true);
    setError(null);
    setAuditMeta(null);
    try {
      const r = await fetch(`/api/v1/traces/${target}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`${r.status} — audit not found`);
      setTrace(await r.json());

      // Also fetch audit report for rule_pack_hash + created_at (non-blocking)
      const h = { Authorization: `Bearer ${token}` };
      fetch(`/api/v1/audits/${target}`, { headers: h })
        .then((ar) => ar.ok ? ar.json() : null)
        .then((ad) => { if (ad) setAuditMeta(ad); })
        .catch(() => {});
    } catch (e) {
      setError(e.message);
      setTrace(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>TRACE View</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Select a recent trace or enter an Audit ID to view its 6-step TRACE pipeline timeline.
      </p>

      {/* Recent traces */}
      {(recentLoading || recent.length > 0) && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>Recent Traces</div>
          {recentLoading ? (
            <div style={{ fontSize: 13, color: "#9ca3af" }}>Loading recent traces…</div>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {recent.map((a) => {
                const id = a.audit_id || a.id;
                const score = a.risk_score != null ? Math.round(a.risk_score * 100) : null;
                const color = score >= 70 ? "#dc2626" : score >= 40 ? "#ca8a04" : "#16a34a";
                return (
                  <button
                    key={id}
                    onClick={() => load(id)}
                    style={{
                      padding: "5px 10px", borderRadius: 6, border: "1px solid #e5e7eb",
                      background: auditId === id ? "#f0fdf4" : "#f8fafc",
                      cursor: "pointer", fontSize: 12, fontFamily: "monospace",
                      color: "#374151", display: "flex", alignItems: "center", gap: 6,
                    }}
                  >
                    {id.slice(0, 8)}…
                    {score != null && (
                      <span style={{ fontWeight: 700, color }}>{score}</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

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
          onClick={() => load()}
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
              {/* Rule Pack badge — shows which pack version was active for this scan */}
              {(auditMeta?.rule_pack_hash || auditMeta?.rule_pack_version) && (
                <span style={{
                  background: "#eff6ff", color: "#1d4ed8",
                  border: "1px solid #bfdbfe", padding: "2px 8px",
                  borderRadius: 6, fontSize: 11, fontFamily: "monospace",
                  display: "flex", alignItems: "center", gap: 4,
                }}>
                  📦 Rule Pack{" "}
                  {auditMeta.rule_pack_version
                    ? `v${auditMeta.rule_pack_version}`
                    : auditMeta.rule_pack_hash?.slice(0, 8) + "…"}
                </span>
              )}
              {auditMeta?.created_at && (
                <span style={{ fontSize: 11, color: "#9ca3af" }}>
                  {new Date(auditMeta.created_at).toLocaleString()}
                </span>
              )}
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
