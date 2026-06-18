import React, { useEffect, useState } from "react";
import { TRACE_METHODOLOGY_READY } from "../config/traceGate";

const STEPS = [
  { key: "ingest",    label: "1. Ingest" },
  { key: "classify",  label: "2. Classify" },
  { key: "match",     label: "3. Match" },
  { key: "score",     label: "4. Score" },
  { key: "explain",   label: "5. Explain" },
  { key: "remediate", label: "6. Remediate" },
];

// STORY-TRACE-001: the timeline endpoint (GET /api/v1/audit/{id}/trace) returns
// `steps` as an ARRAY of {key, status, detail, executive_summary, rules_fired,
// confidence}. Normalize it to the render model the screen binds against —
// keyed by step, with truthful per-step status (NO all-green fallback).
export function normalizeTrace(raw) {
  const stepsArr = Array.isArray(raw?.steps) ? raw.steps : [];
  const byKey = {};
  for (const s of stepsArr) {
    if (s && s.key) byKey[String(s.key).toLowerCase()] = s;
  }
  // A real result is any step with a concrete pass/warn/fail/done status.
  const hasResults = stepsArr.some(
    (s) => s && s.status && s.status !== "pending"
  );
  return {
    byKey,
    stepCount: stepsArr.length,
    hasResults,
    auditStatus: raw?.audit_status ?? null,
    riskScore: raw?.risk_score ?? null,
    modelVersion: raw?.model_version ?? null,
    executiveMode: !!raw?.executive_mode,
    // STORY-TRACE-004: server-computed integrity verdict (null when absent).
    integrity: raw?.integrity ?? null,
    // STORY-TRACE-008: provenance triple (rule-pack hash + model + scan time).
    rulePackHash: raw?.rule_pack_hash ?? null,
    scannedAt: raw?.scanned_at ?? null,
  };
}

// STORY-TRACE-008: a provenance value the engine never recorded must read as an
// explicit "unavailable" — never a blank that implies there was no versioning.
const _PROVENANCE_UNAVAILABLE = "provenance-unavailable";

function _isUnavailable(v) {
  return v == null || v === "" || v === _PROVENANCE_UNAVAILABLE;
}

function _fmtScanTime(iso) {
  if (_isUnavailable(iso)) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  // Stable, unambiguous, timezone-explicit (UTC) format for the audit file.
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
}

// A single read-only provenance field: shows the value or an explicit
// "unavailable" placeholder, with the full value available on hover (title).
function ProvField({ label, value, full }) {
  const unavailable = _isUnavailable(value);
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", gap: 4, fontSize: 11 }}>
      <span style={{ color: "#9ca3af", textTransform: "uppercase", letterSpacing: 0.4 }}>{label}</span>
      <span
        title={unavailable ? "Not recorded for this audit" : (full || value)}
        style={{
          fontFamily: "monospace",
          color: unavailable ? "#9ca3af" : "#374151",
          fontStyle: unavailable ? "italic" : "normal",
          userSelect: "text",
        }}
      >
        {unavailable ? "unavailable" : value}
      </span>
    </span>
  );
}

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

export default function TraceView({ token, initialAuditId, user, onNavigate, methodologyReady = TRACE_METHODOLOGY_READY }) {
  // STORY-TRACE-005 (ADR-004 TRACE View Gate): in an enterprise/demo presentation
  // context, full TRACE reasoning (technical mode) is gated until the "How SARO
  // Reasons" transparency document is published. Demo sessions (S-205 demo tokens:
  // role=demo_viewer / read_only) are the enterprise/demo context; internal staff
  // sessions are not gated. Default-deny: methodologyReady defaults to the config
  // flag, which is false when unset.
  const demoContext = user?.role === "demo_viewer" || !!user?.read_only;
  const methodologyGated = demoContext && !methodologyReady;

  const [auditId, setAuditId]   = useState(initialAuditId || "");
  const [trace, setTrace]       = useState(null);
  const [auditMeta, setAuditMeta] = useState(null); // rule_pack_hash + created_at from audit report
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [mode, setMode]         = useState("summary");
  const [recent, setRecent]     = useState([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState(false);

  useEffect(() => {
    async function loadRecent() {
      setRecentLoading(true);
      setRecentError(false);
      try {
        const r = await fetch("/api/v1/audits?limit=10&sort=desc", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) {
          setRecent(await r.json());
        } else {
          // STORY-TRACE-007: keep an access/transient failure distinct from a
          // legitimately empty tenant (which is a valid "no recent traces" state).
          setRecentError(true);
        }
      } catch {
        setRecentError(true); // non-fatal — recent list is a convenience feature
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
      // STORY-TRACE-001: the timeline endpoint returns the true 6-step pipeline
      // (steps as an array with real per-gate status), not the raw trace rows.
      const r = await fetch(`/api/v1/audit/${target}/trace`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(`${r.status} — audit not found`);
      setTrace(normalizeTrace(await r.json()));

      // Also fetch audit report for rule_pack_hash + created_at (non-blocking)
      fetch(`/api/v1/audits/${target}`, { headers: { Authorization: `Bearer ${token}` } })
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
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>TRACE View</h1>
        {/* STORY-TRACE-005 / ADR-004: methodology transparency affordance, always visible */}
        <button
          type="button"
          onClick={() => onNavigate?.("how_saro_reasons")}
          style={{ background: "none", border: "none", padding: 0, color: "#0d9488", cursor: "pointer", fontSize: 13, textDecoration: "underline" }}
        >
          How SARO Reasons ↗
        </button>
      </div>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Select a recent trace or enter an Audit ID to view its 6-step TRACE pipeline timeline.
      </p>

      {/* STORY-TRACE-005: ADR-004 gate notice for enterprise/demo sessions when the
          transparency document is not yet published. */}
      {methodologyGated && (
        <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 8, padding: "10px 14px", color: "#92400e", fontSize: 13, marginBottom: 20 }}>
          ⓘ Full TRACE reasoning (technical mode) is unavailable in this demo until the
          {" "}
          <button type="button" onClick={() => onNavigate?.("how_saro_reasons")} style={{ background: "none", border: "none", padding: 0, color: "#92400e", cursor: "pointer", textDecoration: "underline", font: "inherit" }}>
            “How SARO Reasons”
          </button>
          {" "}transparency document is published (ADR-004 TRACE View Gate).
        </div>
      )}

      {/* Recent traces */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8 }}>Recent Traces</div>
        {recentLoading ? (
          <div style={{ fontSize: 13, color: "#9ca3af" }}>Loading recent traces…</div>
        ) : recentError ? (
          <div style={{ fontSize: 13, color: "#9ca3af" }}>Recent traces are unavailable right now.</div>
        ) : recent.length === 0 ? (
          <div style={{ fontSize: 13, color: "#9ca3af" }}>No recent traces for this tenant yet.</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {recent.map((a) => {
              const id = a.audit_id || a.id;
              // STORY-TRACE-007: the audits list returns `overall_risk_score`
              // (0–1); `risk_score` is kept only as a defensive fallback. Scale
              // once. A null score omits the number (no "0"/"NaN").
              const raw = a.overall_risk_score ?? a.risk_score;
              const score = raw != null ? Math.round(raw * 100) : null;
              const color = score == null
                ? "#9ca3af"
                : score >= 70 ? "#dc2626" : score >= 40 ? "#ca8a04" : "#16a34a";
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
                {(auditMeta?.audit_id || auditId).slice(0, 16)}…
              </div>
              <StatusBadge status={trace.auditStatus} />
              <RiskChip score={trace.riskScore} />
              <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                {["summary", "technical"].map((m) => {
                  // STORY-TRACE-005: technical mode is gated in enterprise/demo
                  // sessions until the transparency doc is published.
                  const disabled = m === "technical" && methodologyGated;
                  return (
                    <button
                      key={m}
                      disabled={disabled}
                      title={disabled ? "Gated until the “How SARO Reasons” doc is published (ADR-004)" : undefined}
                      onClick={() => !disabled && setMode(m)}
                      style={{
                        padding: "4px 12px", borderRadius: 20, fontSize: 12,
                        background: mode === m ? "#0d9488" : "#f3f4f6",
                        color: mode === m ? "#fff" : "#374151",
                        border: "none", cursor: disabled ? "not-allowed" : "pointer",
                        opacity: disabled ? 0.5 : 1,
                      }}
                    >
                      {m.charAt(0).toUpperCase() + m.slice(1)}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* STORY-TRACE-008: provenance triple — rule-pack hash + model version
                + scan timestamp as a first-class, copy-friendly, labeled block.
                model_version comes from the timeline (not the audit-report fetch);
                each missing field reads "unavailable", never blank. */}
            <div style={{
              marginTop: 12, paddingTop: 12, borderTop: "1px solid #f3f4f6",
              display: "flex", flexWrap: "wrap", gap: 16, alignItems: "baseline",
            }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: "#9ca3af", textTransform: "uppercase", letterSpacing: 0.6 }}>Provenance</span>
              <ProvField
                label="Rule pack"
                value={(trace.rulePackHash || auditMeta?.rule_pack_hash) ? (trace.rulePackHash || auditMeta?.rule_pack_hash).slice(0, 12) + "…" : null}
                full={trace.rulePackHash || auditMeta?.rule_pack_hash}
              />
              <ProvField label="Model" value={trace.modelVersion} />
              <ProvField label="Scanned" value={_fmtScanTime(trace.scannedAt || auditMeta?.created_at)} />
            </div>
          </div>

          {/* STORY-TRACE-001: a trace with no records reads all-pending with an
              explicit note — never the old all-green "done" fallback. */}
          {!trace.hasResults && (
            <div style={{ background: "#f9fafb", border: "1px dashed #d1d5db", borderRadius: 8, padding: "10px 14px", color: "#6b7280", fontSize: 13, marginBottom: 12 }}>
              No trace records for this audit yet — all pipeline steps are pending.
            </div>
          )}

          {/* Pipeline timeline */}
          <div style={{ display: "flex", gap: 8, marginBottom: 20, overflowX: "auto", paddingBottom: 4 }}>
            {STEPS.map((step, i) => {
              const stepData = trace.byKey[step.key] || {};
              const status = stepData.status || "pending";
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
            const stepData = trace.byKey[step.key];
            if (!stepData) return null;
            const summaryText = stepData.detail || stepData.executive_summary;
            return (
              <div key={step.key} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{step.label}</span>
                  <StatusBadge status={stepData.status} />
                  {stepData.confidence != null && (
                    <span style={{ fontSize: 12, color: "#6b7280" }}>
                      Confidence: {(stepData.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {mode === "summary" && (
                  summaryText
                    ? <p style={{ fontSize: 13, color: "#374151", margin: 0 }}>{summaryText}</p>
                    : <p style={{ fontSize: 13, color: "#9ca3af", margin: 0, fontStyle: "italic" }}>No detail for this step.</p>
                )}
                {mode === "technical" && !methodologyGated && (
                  <pre style={{ fontSize: 11, background: "#f8fafc", padding: 10, borderRadius: 6, overflow: "auto", margin: 0 }}>
                    {JSON.stringify(stepData, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}

          {/* STORY-TRACE-004: honest integrity banner — a positive claim renders
              ONLY when the backend confirms a real HMAC signature match; otherwise
              the state is neutral "not verified", never a green "verified". */}
          {trace.integrity && (
            trace.integrity.verified ? (
              <div style={{
                padding: "10px 14px", borderRadius: 8, marginTop: 8,
                background: "#d1fae5", border: "1px solid #6ee7b7",
                fontSize: 13, color: "#065f46",
              }}>
                ✓ Integrity verified — {trace.integrity.detail}
                {trace.integrity.export_hash && (
                  <> (export hash <code>{trace.integrity.export_hash}…</code>)</>
                )}
                {" "}Evidence for human auditor review.
              </div>
            ) : (
              <div style={{
                padding: "10px 14px", borderRadius: 8, marginTop: 8,
                background: "#f3f4f6", border: "1px solid #d1d5db",
                fontSize: 13, color: "#6b7280",
              }}>
                ⓘ Integrity not verified — {trace.integrity.detail || "verification unavailable for this audit."}
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}
