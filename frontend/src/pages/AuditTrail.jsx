/**
 * Audit Trail — SARO's internal privileged-action hash-chain trail
 * (STORY-META-001, `audit_events` / routers/self_audit.py). Distinct from
 * TRACE View: this is the log of who-did-what-to-SARO-itself (logins, rule
 * pack changes, evidence exports), not the scored prompt+output pipeline.
 *
 * Backend gate mirrors `_require_auditor` in routers/self_audit.py exactly —
 * see Sidebar.jsx PERSONA_TABS — so this page is only ever reachable by a
 * persona the API will actually authorize.
 */
import React, { useState, useEffect, useCallback } from "react";
import { Download, ShieldCheck, ShieldAlert } from "lucide-react";
import { Button, Badge, EmptyState, PageHeader, Skeleton } from "../components/ui/index.jsx";

const OUTCOME_SEVERITY = { SUCCESS: "low", FAILURE: "critical" };

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function truncate(v, n = 12) {
  if (!v) return "—";
  return v.length > n ? `${v.slice(0, n)}…` : v;
}

export default function AuditTrail({ token, user }) {
  const [events, setEvents]   = useState([]);
  const [chain, setChain]     = useState(null);
  const [scope, setScope]     = useState("tenant");
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [exporting, setExporting] = useState(false);

  // _resolve_tenant() in routers/self_audit.py 403s scope=system unless the
  // account's base role is super_admin/operator — persona-only ai_auditor
  // access never gets the toggle.
  const canUseSystemScope = ["super_admin", "operator"].includes(user?.role);

  const load = useCallback(async (opts = {}) => {
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams({ scope, ...(opts.export ? { export: "true" } : {}) });
      const r = await fetch(`/api/v1/audit/events?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) throw new Error(r.status === 403 ? "Not authorized for this audit scope" : `${r.status}`);
      const d = await r.json();
      setEvents(d.events || []);
      setChain(d.chain_verification || null);
      return d;
    } catch (e) {
      setError(`Could not load audit trail: ${e.message}`);
      return null;
    } finally {
      setLoading(false);
    }
  }, [token, scope]);

  useEffect(() => { load(); }, [load]);

  async function handleExport() {
    setExporting(true);
    try {
      // export=true is a write — it records its own EXPORT event (self_audit.py
      // AC-4) — so this only ever runs on explicit click, never on page load.
      await load({ export: true });
    } finally {
      setExporting(false);
    }
  }

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Audit Trail"
        subtitle="SARO's own privileged-action log — logins, rule-pack changes, evidence exports — hash-chained per tenant."
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>Audit Trail</span></>}
        actions={
          <>
            {canUseSystemScope && (
              <div style={{ display: "flex", border: "1px solid var(--color-border-default)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
                {["tenant", "system"].map((s) => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    style={{
                      padding: "6px 12px", border: "none", cursor: "pointer",
                      background: scope === s ? "var(--color-info-bg)" : "var(--color-bg-surface)",
                      color: scope === s ? "var(--color-info)" : "var(--color-text-muted)",
                      fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
                      textTransform: "capitalize",
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <Button variant="secondary" size="sm" onClick={handleExport} loading={exporting} disabled={!events.length}>
              <Download size={14} /> Export (records EXPORT event)
            </Button>
          </>
        }
      />

      <div style={{ padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {error && (
          <div style={{
            padding: "var(--space-3) var(--space-4)", borderRadius: "var(--radius-md)",
            background: "var(--color-danger-bg, #FCEBEB)", color: "var(--color-danger, #791F1F)",
            fontSize: "var(--text-sm)",
          }}>{error}</div>
        )}

        {loading ? (
          <Skeleton height={240} />
        ) : (
          <>
            {chain && (
              <div style={{
                display: "flex", alignItems: "center", gap: "var(--space-2)",
                padding: "var(--space-3) var(--space-4)",
                background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-lg)", fontSize: "var(--text-sm)",
              }}>
                {chain.valid ? (
                  <ShieldCheck size={16} color="var(--color-low)" />
                ) : (
                  <ShieldAlert size={16} color="var(--color-critical)" />
                )}
                <span style={{ color: "var(--color-text-primary)" }}>
                  Hash chain {chain.valid ? "verified intact" : "verification FAILED"}
                </span>
                <span style={{ color: "var(--color-text-muted)" }}>
                  · {events.length} event{events.length === 1 ? "" : "s"} · {scope} scope
                </span>
              </div>
            )}

            {events.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck />}
                title="No audit events in this scope"
                description={
                  canUseSystemScope
                    ? "Switch scope above, or check back after the next privileged action (login, rule-pack change, evidence export)."
                    : "Privileged actions on this tenant will appear here as they happen."
                }
              />
            ) : (
              <div style={{
                background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-lg)", overflow: "auto",
              }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--color-border-subtle)", textAlign: "left" }}>
                      {["Time", "Action", "Actor", "Target", "Outcome", "Seq", "Hash"].map((h) => (
                        <th key={h} style={{
                          padding: "var(--space-3) var(--space-4)", color: "var(--color-text-muted)",
                          fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
                          textTransform: "uppercase", letterSpacing: "0.04em",
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((e) => (
                      <tr key={e.id} style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
                        <td style={{ padding: "var(--space-3) var(--space-4)", color: "var(--color-text-secondary)", whiteSpace: "nowrap" }}>
                          {fmtTime(e.created_at)}
                        </td>
                        <td style={{ padding: "var(--space-3) var(--space-4)", color: "var(--color-text-primary)", fontWeight: "var(--weight-medium)" }}>
                          {e.action_class}
                        </td>
                        <td style={{ padding: "var(--space-3) var(--space-4)", color: "var(--color-text-secondary)" }}>
                          {e.actor}
                        </td>
                        <td style={{ padding: "var(--space-3) var(--space-4)", color: "var(--color-text-secondary)" }}>
                          {e.target_type}{e.target_id ? ` · ${truncate(e.target_id, 8)}` : ""}
                        </td>
                        <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                          <Badge severity={OUTCOME_SEVERITY[e.outcome] || "info"}>{e.outcome}</Badge>
                        </td>
                        <td style={{ padding: "var(--space-3) var(--space-4)", color: "var(--color-text-muted)" }}>
                          {e.seq ?? "—"}
                        </td>
                        <td style={{ padding: "var(--space-3) var(--space-4)", color: "var(--color-text-muted)", fontFamily: "monospace" }} title={e.event_hash}>
                          {truncate(e.event_hash, 10)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* Required disclaimer per COMPLIANCE_CLAIMS_MATRIX.md */}
      <div style={{
        margin: "0 var(--space-6) var(--space-6)",
        padding: "var(--space-3) var(--space-4)",
        background: "var(--color-bg-surface)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-md)",
        fontSize: "var(--text-xs)", color: "var(--color-text-muted)", lineHeight: 1.6,
      }}>
        <em>
          This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification,
          legal advice, or compliance approval. Human review and sign-off by qualified personnel is required
          before any regulatory submission.
        </em>
      </div>
    </div>
  );
}
