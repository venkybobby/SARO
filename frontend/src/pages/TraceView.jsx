import React, { useEffect, useState } from "react";
import { PageHeader, Skeleton } from "../components/ui/index.jsx";
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
// "unavailable" placeholder. When `truncate` is set, a long value (e.g. a hash)
// is shortened for display with the full value kept in the title for citation.
function ProvField({ label, value, truncate }) {
  const unavailable = _isUnavailable(value);
  const display = unavailable
    ? "unavailable"
    : truncate
      ? `${value.slice(0, 12)}…`
      : value;
  return (
    <span style={{ display: "inline-flex", alignItems: "baseline", gap: 4, fontSize: "var(--text-xs)" }}>
      <span style={{ color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.4 }}>{label}</span>
      <span
        title={unavailable ? "Not recorded for this audit" : value}
        style={{
          fontFamily: "var(--font-mono)",
          color: unavailable ? "var(--color-text-muted)" : "var(--color-text-primary)",
          fontStyle: unavailable ? "italic" : "normal",
          userSelect: "text",
        }}
      >
        {display}
      </span>
    </span>
  );
}

// STORY-TRACE-009: status palette mapped onto the shared design tokens.
// Semantics preserved: pass/done = low (green), warn = medium (amber),
// fail = critical (red), pending = neutral.
const STATUS_STYLES = {
  done:    { bg: "var(--color-low-bg)",      color: "var(--color-low)",        border: "var(--color-low-border)",      icon: "✓" },
  pass:    { bg: "var(--color-low-bg)",      color: "var(--color-low)",        border: "var(--color-low-border)",      icon: "✓" },
  warn:    { bg: "var(--color-medium-bg)",   color: "var(--color-medium)",     border: "var(--color-medium-border)",   icon: "⚠" },
  fail:    { bg: "var(--color-critical-bg)", color: "var(--color-critical)",   border: "var(--color-critical-border)", icon: "✗" },
  pending: { bg: "var(--color-bg-overlay)",  color: "var(--color-text-muted)", border: "var(--color-border-subtle)",   icon: "…" },
};

// Risk thresholds preserved: ≥70 critical, ≥40 medium, else low.
function _riskTone(score) {
  return score >= 70 ? "critical" : score >= 40 ? "medium" : "low";
}

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending;
  return (
    <span style={{ background: s.bg, color: s.color, padding: "2px 8px", borderRadius: "var(--radius-sm)", fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)" }}>
      {s.icon} {(status || "pending").toUpperCase()}
    </span>
  );
}

function RiskChip({ score }) {
  if (score == null) return null;
  const s = Math.round(score * 100);
  const tone = _riskTone(s);
  return (
    <span style={{
      background: `var(--color-${tone}-bg)`, color: `var(--color-${tone})`,
      border: `1px solid var(--color-${tone}-border)`,
      padding: "2px 10px", borderRadius: "var(--radius-lg)",
      fontWeight: "var(--weight-semibold)", fontSize: "var(--text-base)",
    }}>
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
  const [loadedId, setLoadedId] = useState(null); // id of the trace actually displayed
  const [trace, setTrace]       = useState(null);
  const [auditMeta, setAuditMeta] = useState(null); // rule_pack_hash + created_at from audit report
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [mode, setMode]         = useState("summary");
  const [recent, setRecent]     = useState([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState(false);
  const [exporting, setExporting] = useState(null);   // 'json' | 'pdf' | null
  const [exportError, setExportError] = useState(null);

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
    setLoadedId(null);
    try {
      // STORY-TRACE-001: the timeline endpoint returns the true 6-step pipeline
      // (steps as an array with real per-gate status), not the raw trace rows.
      const r = await fetch(`/api/v1/audit/${target}/trace`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        // STORY-TRACE-010: distinguish no-access (403) from genuinely-missing
        // (404) from a transient server failure — they are NOT all "not found".
        setTrace(null);
        if (r.status === 403) {
          setError({ kind: "forbidden", message: "You don't have access to this audit's trace." });
        } else if (r.status === 404) {
          setError({ kind: "notfound", message: "Audit not found — there is no trace for this ID." });
        } else {
          setError({ kind: "transient", message: `Couldn't load the trace (server error ${r.status}).` });
        }
        return;
      }
      setTrace(normalizeTrace(await r.json()));
      setLoadedId(target); // the id that produced the displayed trace

      // Also fetch audit report for rule_pack_hash + created_at (non-blocking)
      fetch(`/api/v1/audits/${target}`, { headers: { Authorization: `Bearer ${token}` } })
        .then((ar) => ar.ok ? ar.json() : null)
        .then((ad) => { if (ad) setAuditMeta(ad); })
        .catch(() => {});
    } catch {
      setTrace(null);
      setError({ kind: "transient", message: "Network error — couldn't reach the server. Check your connection and retry." });
    } finally {
      setLoading(false);
    }
  }

  // STORY-TRACE-006: pull the signed evidence bundle (JSON or PDF) for the loaded
  // audit. Uses the existing auth-header fetch; a non-200 surfaces an inline error
  // and never saves an empty/corrupt file. Cross-tenant/forbidden audits return
  // 403/404 (tenant scope + role gate from STORY-TRACE-002/003) and are messaged.
  async function exportEvidence(fmt) {
    // Export the trace that is actually displayed, not whatever is currently
    // typed in the search box (reviewer MINOR on STORY-TRACE-006).
    const target = loadedId;
    if (!target) return;
    setExportError(null);
    setExporting(fmt);
    try {
      const url = `/api/v1/audit/${target}/export/${fmt === "pdf" ? "pdf" : "json"}`;
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) {
        throw new Error(
          r.status === 403 ? "You don't have access to export this audit."
            : r.status === 404 ? "Audit not found — nothing to export."
              : `Export failed (${r.status}).`
        );
      }
      const blob = await r.blob();
      // Prefer the server-provided filename (PDF sets Content-Disposition);
      // fall back to a client-derived name for the JSON body response.
      const cd = r.headers.get?.("Content-Disposition") || "";
      const m = cd.match(/filename="?([^"]+)"?/);
      const filename = m ? m[1] : `saro-trace-${target.slice(0, 8)}.${fmt === "pdf" ? "pdf" : "json"}`;
      const objUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objUrl);
    } catch (e) {
      setExportError(e.message || "Export failed.");
    } finally {
      setExporting(null);
    }
  }

  const pillStyle = (active, disabled) => ({
    padding: "4px 12px", borderRadius: "var(--radius-lg)", fontSize: "var(--text-sm)",
    background: active ? "var(--color-info)" : "var(--color-bg-overlay)",
    color: active ? "var(--color-text-inverse)" : "var(--color-text-primary)",
    border: "none", cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  });

  return (
    <div>
      <PageHeader
        title="TRACE View"
        subtitle="Inspect an audit's 6-step TRACE pipeline timeline and pull signed evidence for the audit file."
        actions={
          /* STORY-TRACE-005 / ADR-004: methodology transparency affordance, always visible */
          <button
            type="button"
            onClick={() => onNavigate?.("how_saro_reasons")}
            style={{ background: "none", border: "none", padding: 0, color: "var(--color-info)", cursor: "pointer", fontSize: "var(--text-sm)", textDecoration: "underline" }}
          >
            How SARO Reasons ↗
          </button>
        }
      />

      <div style={{ padding: "var(--space-6)", maxWidth: 1000 }}>
      {/* STORY-TRACE-005: ADR-004 gate notice for enterprise/demo sessions when the
          transparency document is not yet published. */}
      {methodologyGated && (
        <div style={{ background: "var(--color-medium-bg)", border: "1px solid var(--color-medium-border)", borderRadius: "var(--radius-md)", padding: "10px 14px", color: "var(--color-medium)", fontSize: "var(--text-sm)", marginBottom: "var(--space-5)" }}>
          ⓘ Full TRACE reasoning (technical mode) is unavailable in this demo until the
          {" "}
          <button type="button" onClick={() => onNavigate?.("how_saro_reasons")} style={{ background: "none", border: "none", padding: 0, color: "var(--color-medium)", cursor: "pointer", textDecoration: "underline", font: "inherit" }}>
            “How SARO Reasons”
          </button>
          {" "}transparency document is published (ADR-004 TRACE View Gate).
        </div>
      )}

      {/* Recent traces */}
      <div style={{ marginBottom: "var(--space-5)" }}>
        <div style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)", marginBottom: "var(--space-2)" }}>Recent Traces</div>
        {recentLoading ? (
          <div style={{ display: "flex", gap: 6 }}>
            <Skeleton width={90} height={28} /><Skeleton width={90} height={28} /><Skeleton width={90} height={28} />
          </div>
        ) : recentError ? (
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>Recent traces are unavailable right now.</div>
        ) : recent.length === 0 ? (
          <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>No recent traces for this tenant yet.</div>
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
                ? "var(--color-text-muted)"
                : `var(--color-${_riskTone(score)})`;
              return (
                <button
                  key={id}
                  onClick={() => load(id)}
                  style={{
                    padding: "5px 10px", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-default)",
                    background: auditId === id ? "var(--color-info-bg)" : "var(--color-bg-overlay)",
                    cursor: "pointer", fontSize: "var(--text-xs)", fontFamily: "var(--font-mono)",
                    color: "var(--color-text-primary)", display: "flex", alignItems: "center", gap: 6,
                  }}
                >
                  {id.slice(0, 8)}…
                  {score != null && (
                    <span style={{ fontWeight: "var(--weight-semibold)", color }}>{score}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Search bar */}
      <div style={{ display: "flex", gap: 8, marginBottom: "var(--space-6)" }}>
        <input
          value={auditId}
          onChange={(e) => setAuditId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          placeholder="Audit ID (UUID)…"
          style={{ flex: 1, padding: "10px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-default)", fontSize: "var(--text-base)", background: "var(--color-bg-elevated)", color: "var(--color-text-primary)" }}
        />
        <button
          onClick={() => load()}
          disabled={loading}
          style={{ padding: "10px 20px", background: "var(--color-info)", color: "var(--color-text-inverse)", border: "none", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "var(--text-base)" }}
        >
          {loading ? "Loading…" : "Load TRACE"}
        </button>
      </div>

      {/* STORY-TRACE-010: loading / error / loaded are mutually exclusive.
          Loading shows real skeletons (not bare text); errors are differentiated
          (403 vs 404 vs transient) with a retry affordance for transient failures
          that re-fetches only the trace. */}
      {loading ? (
        <div aria-busy="true">
          <Skeleton width="100%" height={72} />
          <div style={{ display: "flex", gap: 8, marginTop: "var(--space-4)" }}>
            {STEPS.map((s) => <Skeleton key={s.key} width={100} height={56} />)}
          </div>
          <div style={{ marginTop: "var(--space-4)" }}><Skeleton width="100%" height={96} /></div>
        </div>
      ) : error ? (
        <div
          role="alert"
          style={{
            background: error.kind === "transient" ? "var(--color-bg-overlay)" : "var(--color-critical-bg)",
            border: `1px solid ${error.kind === "transient" ? "var(--color-border-default)" : "var(--color-critical-border)"}`,
            borderRadius: "var(--radius-md)", padding: "12px 16px",
            color: error.kind === "transient" ? "var(--color-text-secondary)" : "var(--color-critical)",
            fontSize: "var(--text-sm)", marginBottom: "var(--space-4)",
            display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
          }}
        >
          <span>{error.kind === "forbidden" ? "🔒" : error.kind === "notfound" ? "🔍" : "⚠"} {error.message}</span>
          {error.kind === "transient" && (
            <button
              onClick={() => load(auditId)}
              style={{ padding: "4px 12px", borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)", background: "var(--color-info)", color: "var(--color-text-inverse)", border: "none", cursor: "pointer" }}
            >
              Retry
            </button>
          )}
        </div>
      ) : trace ? (
        <>
          {/* Header */}
          <div style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-default)", borderRadius: "var(--radius-md)", padding: "var(--space-4)", marginBottom: "var(--space-4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
                {(auditMeta?.audit_id || auditId).slice(0, 16)}…
              </div>
              <StatusBadge status={trace.auditStatus} />
              <RiskChip score={trace.riskScore} />
              <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
                {/* STORY-TRACE-006: signed evidence export actions */}
                {["json", "pdf"].map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => exportEvidence(fmt)}
                    disabled={!loadedId || exporting === fmt}
                    style={{
                      padding: "4px 10px", borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)",
                      background: "var(--color-bg-surface)", color: "var(--color-info)",
                      border: "1px solid var(--color-info)",
                      cursor: !loadedId || exporting === fmt ? "not-allowed" : "pointer",
                      opacity: !loadedId || exporting === fmt ? 0.6 : 1,
                    }}
                  >
                    {exporting === fmt ? "Exporting…" : `Export ${fmt.toUpperCase()}`}
                  </button>
                ))}
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
                      style={pillStyle(mode === m, disabled)}
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
              marginTop: "var(--space-3)", paddingTop: "var(--space-3)", borderTop: "1px solid var(--color-border-subtle)",
              display: "flex", flexWrap: "wrap", gap: 16, alignItems: "baseline",
            }}>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.6 }}>Provenance</span>
              <ProvField label="Rule pack" value={trace.rulePackHash || auditMeta?.rule_pack_hash} truncate />
              <ProvField label="Model" value={trace.modelVersion} />
              <ProvField label="Scanned" value={_fmtScanTime(trace.scannedAt || auditMeta?.created_at)} />
            </div>
          </div>

          {/* STORY-TRACE-006: inline export error — never a silent/corrupt download */}
          {exportError && (
            <div style={{ background: "var(--color-critical-bg)", border: "1px solid var(--color-critical-border)", borderRadius: "var(--radius-md)", padding: "8px 12px", color: "var(--color-critical)", fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
              ⚠ {exportError}
            </div>
          )}

          {/* STORY-TRACE-001: a trace with no records reads all-pending with an
              explicit note — never the old all-green "done" fallback. */}
          {!trace.hasResults && (
            <div style={{ background: "var(--color-bg-overlay)", border: "1px dashed var(--color-border-default)", borderRadius: "var(--radius-md)", padding: "10px 14px", color: "var(--color-text-secondary)", fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
              No trace records for this audit yet — all pipeline steps are pending.
            </div>
          )}

          {/* Pipeline timeline (horizontally scrollable on narrow viewports) */}
          <div style={{ display: "flex", gap: 8, marginBottom: "var(--space-5)", overflowX: "auto", paddingBottom: 4 }}>
            {STEPS.map((step, i) => {
              const stepData = trace.byKey[step.key] || {};
              const status = stepData.status || "pending";
              const ss = STATUS_STYLES[status] || STATUS_STYLES.pending;
              return (
                <React.Fragment key={step.key}>
                  <div style={{
                    padding: "10px 14px", borderRadius: "var(--radius-md)", background: ss.bg, color: ss.color,
                    minWidth: 100, textAlign: "center", border: `1px solid ${ss.border}`,
                  }}>
                    <div style={{ fontWeight: "var(--weight-semibold)", fontSize: "var(--text-sm)" }}>{step.label}</div>
                    <div style={{ fontSize: "var(--text-xs)", marginTop: 2 }}>{ss.icon} {status}</div>
                  </div>
                  {i < STEPS.length - 1 && (
                    <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-lg)", display: "flex", alignItems: "center" }}>→</div>
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
              <div key={step.key} style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-default)", borderRadius: "var(--radius-md)", padding: "var(--space-4)", marginBottom: "var(--space-3)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "var(--space-2)" }}>
                  <span style={{ fontWeight: "var(--weight-semibold)", fontSize: "var(--text-base)" }}>{step.label}</span>
                  <StatusBadge status={stepData.status} />
                  {stepData.confidence != null && (
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
                      Confidence: {(stepData.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {mode === "summary" && (
                  summaryText
                    ? <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-primary)", margin: 0 }}>{summaryText}</p>
                    : <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)", margin: 0, fontStyle: "italic" }}>No detail for this step.</p>
                )}
                {mode === "technical" && !methodologyGated && (
                  <pre style={{ fontSize: "var(--text-xs)", background: "var(--color-bg-overlay)", padding: 10, borderRadius: "var(--radius-md)", overflow: "auto", margin: 0 }}>
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
                padding: "10px 14px", borderRadius: "var(--radius-md)", marginTop: "var(--space-2)",
                background: "var(--color-low-bg)", border: "1px solid var(--color-low-border)",
                fontSize: "var(--text-sm)", color: "var(--color-low)",
              }}>
                ✓ Integrity verified — {trace.integrity.detail}
                {trace.integrity.export_hash && (
                  <> (export hash <code>{trace.integrity.export_hash}…</code>)</>
                )}
                {" "}Evidence for human auditor review.
              </div>
            ) : (
              <div style={{
                padding: "10px 14px", borderRadius: "var(--radius-md)", marginTop: "var(--space-2)",
                background: "var(--color-bg-overlay)", border: "1px solid var(--color-border-default)",
                fontSize: "var(--text-sm)", color: "var(--color-text-secondary)",
              }}>
                ⓘ Integrity not verified — {trace.integrity.detail || "verification unavailable for this audit."}
              </div>
            )
          )}
        </>
      ) : null}
      </div>
    </div>
  );
}
