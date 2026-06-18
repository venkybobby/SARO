/**
 * Compliance Hub — landing page for compliance_lead persona.
 * Sections: EVF Validation Status, Recent Audits, Governance Docs, QCO Expiry Alerts, Readiness Checklist.
 *
 * CHUB-007: refactored onto the shared design system — PageHeader + design tokens
 * (no hardcoded hex / system-ui literals; colours come from var(--color-*)).
 */
import React, { useEffect, useState } from "react";
import { Button, PageHeader, Skeleton } from "../components/ui/index.jsx";

// Tier badge config — colours are design tokens (paired fg / bg / border).
const TIER_CONFIG = {
  tier_1: { color: "var(--color-low)", bg: "var(--color-low-bg)", border: "var(--color-low-border)", icon: "✅", short: "EXTERNALLY REVIEWED" },
  tier_2: { color: "var(--color-medium)", bg: "var(--color-medium-bg)", border: "var(--color-medium-border)", icon: "⏳", short: "UNDER REVIEW" },
  tier_3: { color: "var(--color-text-secondary)", bg: "var(--color-bg-elevated)", border: "var(--color-border-subtle)", icon: "🔒", short: "INTERNAL ONLY" },
};

const _TIER_FALLBACK = { color: "var(--color-text-secondary)", bg: "var(--color-bg-elevated)", border: "var(--color-border-subtle)", icon: "🔒", short: "INTERNAL ONLY" };

function api(token, path) {
  return fetch(path, { headers: { Authorization: `Bearer ${token}` } }).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  });
}

// CHUB-006: stream a file download from an authenticated GET. On any non-200 the
// caller's onError is invoked with the server's message and NO file is written —
// a 413/error must never produce an empty/corrupt download.
export async function downloadFile({ token, path, filename, onError }) {
  try {
    const r = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) {
      let msg = `Export failed (${r.status})`;
      try {
        const j = await r.json();
        msg = j?.detail?.message || (typeof j?.detail === "string" ? j.detail : msg);
      } catch {
        /* non-JSON body */
      }
      onError(msg);
      return false;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    onError(null);
    return true;
  } catch {
    onError("Export failed — network error");
    return false;
  }
}

function Card({ children, style }) {
  return (
    <div style={{
      background: "var(--color-bg-surface)",
      border: "1px solid var(--color-border-subtle)",
      borderRadius: "var(--radius-lg)",
      padding: "var(--space-4)",
      ...style,
    }}>
      {children}
    </div>
  );
}

function TierBadge({ tier, label, qcoRef, warning }) {
  const cfg = TIER_CONFIG[tier] || _TIER_FALLBACK;
  return (
    <span
      style={{
        background: cfg.bg, color: cfg.color,
        border: `1px solid ${cfg.border}`,
        padding: "2px 8px", borderRadius: "var(--radius-lg)",
        fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
      }}
      title={label || ""}
    >
      {cfg.icon} {cfg.short}{warning ? " · EXPIRED" : ""}{qcoRef ? ` · ${qcoRef}` : ""}
    </span>
  );
}

// ─── STORY-CHUB-001: EVF tier reconciliation ─────────────────────────────────
// Display strings from /compliance-matrix/coverage (regulation_name) must be
// reconciled with enum values from /evf/validation-status. A single canonical
// key drives the join so a coverage % is never shown without its validation tier.

const FW_DISPLAY = {
  EU_AI_ACT: "EU AI Act",
  NIST_AI_RMF: "NIST AI RMF",
  AIGP: "AIGP",
  ISO_42001: "ISO 42001",
};

export function canonicalFramework(s) {
  if (!s) return "";
  const u = String(s).toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (u in FW_DISPLAY) return u;
  if (u.includes("EU") && u.includes("AI") && u.includes("ACT")) return "EU_AI_ACT";
  if (u.includes("NIST")) return "NIST_AI_RMF";
  if (u.includes("ISO") && u.includes("42001")) return "ISO_42001";
  if (u.includes("AIGP")) return "AIGP";
  return u;
}

// CHUB-005: most-recent last_updated across coverage frameworks → provenance line.
export function mostRecentLastUpdated(frameworks) {
  const dates = (Array.isArray(frameworks) ? frameworks : [])
    .map((fw) => fw.last_updated)
    .filter(Boolean)
    .map((d) => String(d).slice(0, 10));
  if (dates.length === 0) return null;
  return dates.sort().at(-1);
}

function isExpired(dateStr) {
  if (!dateStr) return false;
  const t = new Date(dateStr).getTime();
  if (Number.isNaN(t)) return false;
  return t < Date.now();
}

function makeEvfRow(label, coveragePct, status) {
  let tier = (status && status.tier) || "tier_3";
  const qcoRef = (status && status.qco_reference) || null;
  const tierLabel = (status && status.label) || null;
  let warning = false;
  // Anti-overclaiming: an expired Tier 1 QCO must never render as green/validated.
  if (tier === "tier_1" && isExpired(status && status.qco_expiry_date)) {
    tier = "tier_2";
    warning = true;
  }
  return {
    key: label,
    label,
    coveragePct: coveragePct == null ? null : coveragePct,
    tier,
    qcoRef,
    tierLabel,
    warning,
  };
}

/**
 * Single source of truth for the EVF card rows. Guarantees the tier-with-coverage
 * invariant: every returned row has a non-null `tier` (defaulting to tier_3), so a
 * coverage % can never be rendered without a validation tier badge.
 */
export function buildEvfRows({ coverage, statuses, tierUnavailable }) {
  const statusList = Array.isArray(statuses) ? statuses : [];
  const byCanon = new Map();
  for (const s of statusList) {
    byCanon.set(canonicalFramework(s.framework || s.name), s);
  }

  const rows = [];
  const seen = new Set();
  const covFrameworks =
    coverage && Array.isArray(coverage.frameworks) ? coverage.frameworks : [];

  for (const fw of covFrameworks) {
    const label = fw.framework || fw.name || "Unknown";
    const canon = canonicalFramework(label);
    seen.add(canon);
    const status = tierUnavailable ? null : byCanon.get(canon);
    rows.push(makeEvfRow(label, fw.coverage_pct, status));
  }

  // Frameworks present in /validation-status but absent from /coverage must still
  // surface (tier badge only, no coverage bar) — never silently dropped.
  if (!tierUnavailable) {
    for (const s of statusList) {
      const canon = canonicalFramework(s.framework || s.name);
      if (seen.has(canon)) continue;
      seen.add(canon);
      const label = FW_DISPLAY[canon] || s.framework || s.name || "Unknown";
      rows.push(makeEvfRow(label, null, s));
    }
  }

  return rows;
}

function RiskBadge({ score }) {
  const s = score * 100;
  // Thresholds preserved: RED ≥70, AMBER ≥40, GREEN otherwise (now tokenised).
  const t = s >= 70
    ? { c: "var(--color-critical)", bg: "var(--color-critical-bg)", br: "var(--color-critical-border)" }
    : s >= 40
    ? { c: "var(--color-medium)", bg: "var(--color-medium-bg)", br: "var(--color-medium-border)" }
    : { c: "var(--color-low)", bg: "var(--color-low-bg)", br: "var(--color-low-border)" };
  return (
    <span style={{ background: t.bg, color: t.c, border: `1px solid ${t.br}`, padding: "2px 8px", borderRadius: "var(--radius-lg)", fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)" }}>
      {s.toFixed(0)}
    </span>
  );
}

// ─── STORY-010: Compliance Calendar ──────────────────────────────────────────

const KNOWN_FRAMEWORKS = ["eu_ai_act", "nist_ai_rmf", "aigp", "iso_42001"];
const FW_LABELS = {
  eu_ai_act:    "EU AI Act",
  nist_ai_rmf:  "NIST AI RMF",
  aigp:         "AIGP",
  iso_42001:    "ISO 42001",
};

/**
 * Compliance Calendar — pulls EVF validation status and QCO expiry alerts.
 * Shows each framework's review cycle and any upcoming expirations.
 */
function ComplianceCalendar({ token }) {
  const [statuses, setStatuses] = useState([]);
  const [expiries, setExpiries] = useState([]);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    if (!token) return;
    const h = { Authorization: `Bearer ${token}` };
    const safe = (url) => fetch(url, { headers: h }).then((r) => r.ok ? r.json() : []).catch(() => []);
    Promise.all([
      safe("/api/v1/evf/validation-status"),
      safe("/api/v1/evf/qco/expiry-alerts?limit=20"),
    ]).then(([st, ex]) => {
      setStatuses(Array.isArray(st) ? st : []);
      setExpiries(Array.isArray(ex) ? ex : []);
      setLoading(false);
    });
  }, [token]);

  function daysUntil(isoStr) {
    if (!isoStr) return null;
    const d = Math.ceil((new Date(isoStr).getTime() - Date.now()) / 86400000);
    return d;
  }

  if (loading) return <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Loading calendar…</div>;

  const th = { textAlign: "left", padding: "8px 10px", color: "var(--color-text-secondary)", fontWeight: "var(--weight-semibold)" };

  // Build calendar rows: one per framework
  const rows = KNOWN_FRAMEWORKS.map((fw) => {
    const status = statuses.find((s) => s.framework === fw || s.name === fw) || {};
    const tier   = status.tier || status.evf_tier || "tier_3";
    const expiry  = expiries.find((e) => e.framework === fw || e.name === fw);
    const expDate = status.qco_expiry_date || expiry?.expiry_date || null;
    const revDate = status.next_review_date || status.review_date || null;
    const days    = daysUntil(expDate);

    return { fw, label: FW_LABELS[fw] || fw, tier, expDate, revDate, days };
  });

  return (
    <div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--color-border-subtle)" }}>
            <th style={th}>Framework</th>
            <th style={th}>EVF Tier</th>
            <th style={th}>QCO Expiry</th>
            <th style={th}>Next Review</th>
            <th style={th}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ fw, label, tier, expDate, revDate, days }) => {
            const tierCfg = TIER_CONFIG[tier] || _TIER_FALLBACK;
            const urgentColor = days !== null && days < 30 ? "var(--color-critical)" : days !== null && days < 60 ? "var(--color-medium)" : "var(--color-text-primary)";
            return (
              <tr key={fw} style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
                <td style={{ padding: "10px 10px", fontWeight: "var(--weight-semibold)" }}>{label}</td>
                <td style={{ padding: "10px 10px" }}>
                  <span style={{
                    background: tierCfg.bg, color: tierCfg.color,
                    border: `1px solid ${tierCfg.border}`,
                    padding: "2px 7px", borderRadius: "var(--radius-lg)", fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
                  }}>
                    {tierCfg.icon} {tierCfg.short}
                  </span>
                </td>
                <td style={{ padding: "10px 10px", color: urgentColor, fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
                  {expDate
                    ? `${expDate.slice(0, 10)}${days !== null ? ` (${days > 0 ? `${days}d` : "EXPIRED"})` : ""}`
                    : <span style={{ color: "var(--color-text-muted)" }}>—</span>}
                </td>
                <td style={{ padding: "10px 10px", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
                  {revDate ? revDate.slice(0, 10) : <span style={{ color: "var(--color-text-muted)" }}>—</span>}
                </td>
                <td style={{ padding: "10px 10px" }}>
                  {days !== null && days < 0
                    ? <span style={{ color: "var(--color-critical)", fontWeight: "var(--weight-semibold)", fontSize: "var(--text-xs)" }}>⚠ EXPIRED</span>
                    : days !== null && days < 30
                    ? <span style={{ color: "var(--color-critical)", fontWeight: "var(--weight-semibold)", fontSize: "var(--text-xs)" }}>🔴 Urgent</span>
                    : days !== null && days < 60
                    ? <span style={{ color: "var(--color-medium)", fontWeight: "var(--weight-semibold)", fontSize: "var(--text-xs)" }}>🟡 Due soon</span>
                    : tier === "tier_3"
                    ? <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-xs)" }}>Not assessed</span>
                    : <span style={{ color: "var(--color-low)", fontSize: "var(--text-xs)" }}>✓ OK</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {expiries.length === 0 && statuses.length === 0 && (
        <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-xs)", marginTop: 8, fontStyle: "italic" }}>
          No EVF records found — all frameworks are at Tier 3 (Internal Review Only).
        </div>
      )}
      <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 10 }}>
        EVF = External Validation Framework · QCO = Qualified Compliance Opinion.
        Expiry data requires a QCO reference number from an approved SME firm.
      </p>
    </div>
  );
}

export default function ComplianceHub({ token, tenantId, onNavigate }) {
  const [coverage, setCoverage] = useState(null);
  const [audits, setAudits] = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [readinessError, setReadinessError] = useState(false);
  const [error, setError] = useState(null);
  const [statuses, setStatuses] = useState([]);
  const [tierUnavailable, setTierUnavailable] = useState(false);
  const [auditsError, setAuditsError] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    api(token, `/api/v1/compliance-matrix/coverage?tenant_id=${tenantId}&window=30d`)
      .then(setCoverage)
      .catch(() => setError("Coverage data unavailable"));
    // Tier data is sourced from /evf/validation-status, not /coverage. A failure
    // here degrades every framework to Tier 3 — it never blanks the coverage card.
    api(token, `/api/v1/evf/validation-status`)
      .then((d) => {
        setStatuses(Array.isArray(d) ? d : []);
        setTierUnavailable(false);
      })
      .catch(() => {
        setStatuses([]);
        setTierUnavailable(true);
      });
    api(token, `/api/v1/audits?tenant_id=${tenantId}&limit=10&sort=desc`)
      .then((d) => {
        setAudits(Array.isArray(d) ? d : d.items || []);
        setAuditsError(false);
      })
      // CHUB-002 AC-5: surface the failure instead of swallowing it — a 403 or
      // network error must be visibly distinct from a legitimately empty table.
      .catch(() => setAuditsError(true));
    // CHUB-004: readiness checklist is persisted per tenant, not in-memory.
    api(token, `/api/v1/compliance/readiness`)
      .then((d) => {
        setReadiness(d);
        setReadinessError(false);
      })
      .catch(() => setReadinessError(true));
  }, [token, tenantId]);

  const evfRows = buildEvfRows({ coverage, statuses, tierUnavailable });

  // CHUB-004: persist a manual item toggle; derived (read-only) items are ignored.
  function toggleReadiness(item) {
    if (!item.editable) return;
    const next = !item.completed;
    fetch(`/api/v1/compliance/readiness/${item.key}`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ completed: next }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(() => {
        setReadiness((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((it) =>
                  it.key === item.key ? { ...it, completed: next } : it
                ),
              }
            : prev
        );
        setReadinessError(false);
      })
      .catch(() => setReadinessError(true));
  }

  const actions = (
    <>
      <Button
        variant="secondary"
        size="sm"
        onClick={() =>
          downloadFile({
            token,
            path: "/api/v1/compliance-matrix/export",
            filename: "saro-compliance-matrix.csv",
            onError: setActionError,
          })
        }
      >
        Export matrix (CSV)
      </Button>
      <span title={audits.length === 0 ? "No data to report yet" : undefined}>
        <Button
          variant="secondary"
          size="sm"
          disabled={audits.length === 0}
          onClick={() =>
            downloadFile({
              token,
              path: "/api/v1/risk/board-export",
              filename: "saro-board-report.pdf",
              onError: setActionError,
            })
          }
        >
          Generate board report
        </Button>
      </span>
    </>
  );

  return (
    <div style={{ fontFamily: "var(--font-body)", maxWidth: 1200 }}>
      <PageHeader
        title="Compliance Hub"
        subtitle="EVF validation status, recent audits, and readiness tracking for compliance leads."
        actions={actions}
      />

      <div style={{ padding: "var(--space-6)" }}>
        {actionError && (
          <div style={{ color: "var(--color-critical)", fontSize: "var(--text-xs)", marginBottom: "var(--space-4)" }}>⚠ {actionError}</div>
        )}

        {/* CHUB-005: overall matrix-coverage headline + provenance */}
        <Card style={{ marginBottom: "var(--space-5)" }}>
          {error ? (
            <div>
              <div style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)" }}>—</div>
              <div style={{ color: "var(--color-critical)", fontSize: "var(--text-sm)" }}>⚠ {error}</div>
            </div>
          ) : coverage == null ? (
            <div data-testid="coverage-headline-loading">
              <Skeleton width={220} height={34} />
              <div style={{ marginTop: 8 }}><Skeleton width={320} height={14} /></div>
            </div>
          ) : coverage.total_rules === 0 ? (
            <div style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-md)" }}>No matrix data yet</div>
          ) : (
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                <span style={{ fontSize: "var(--text-2xl)", fontWeight: "var(--weight-semibold)", color: "var(--color-info)" }}>
                  {coverage.overall_coverage_pct}%
                </span>
                <span style={{ fontSize: "var(--text-base)", color: "var(--color-text-primary)", fontWeight: "var(--weight-semibold)" }}>Matrix coverage</span>
              </div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginTop: 4 }}>
                {coverage.framework_count} frameworks · {coverage.total_rules} rules
              </div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 4 }}>
                as of {mostRecentLastUpdated(coverage.frameworks) || "—"}
              </div>
            </div>
          )}
        </Card>

        {/* EVF Validation Status */}
        <Card style={{ marginBottom: "var(--space-5)" }}>
          <h2 style={{ fontSize: "var(--text-md)", marginBottom: "var(--space-4)", color: "var(--color-text-primary)" }}>EVF Validation Status</h2>
          {error && <div style={{ color: "var(--color-critical)", marginBottom: "var(--space-3)", fontSize: "var(--text-sm)" }}>⚠ {error}</div>}
          {tierUnavailable && (
            <div style={{ color: "var(--color-medium)", marginBottom: "var(--space-3)", fontSize: "var(--text-xs)" }}>
              ⚠ Validation status unavailable — treated as internal only.
            </div>
          )}
          {coverage?.frameworks || evfRows.length > 0 ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "var(--space-3)" }}>
              {evfRows.map((row) => (
                <div
                  key={row.key}
                  role="button"
                  tabIndex={0}
                  onClick={() => onNavigate?.("coverage_gap", { framework: row.label })}
                  onKeyDown={(e) => { if (e.key === "Enter") onNavigate?.("coverage_gap", { framework: row.label }); }}
                  style={{ border: "1px solid var(--color-border-subtle)", borderRadius: "var(--radius-lg)", padding: "var(--space-3)", cursor: "pointer" }}
                  title={`View compliance matrix for ${row.label}`}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <span style={{ fontWeight: "var(--weight-semibold)", fontSize: "var(--text-sm)", color: "var(--color-text-primary)" }}>{row.label}</span>
                    {row.coveragePct != null && (
                      <span style={{ fontSize: "var(--text-sm)", color: "var(--color-info)" }}>{row.coveragePct.toFixed(1)}%</span>
                    )}
                  </div>
                  {row.coveragePct != null && (
                    <div style={{ height: 4, background: "var(--color-bg-elevated)", borderRadius: "var(--radius-sm)", marginBottom: 8 }}>
                      <div style={{ height: 4, width: `${row.coveragePct}%`, background: "var(--color-info)", borderRadius: "var(--radius-sm)" }} />
                    </div>
                  )}
                  {/* Invariant: every row renders a tier badge — never a coverage % alone. */}
                  <TierBadge tier={row.tier} label={row.tierLabel} qcoRef={row.qcoRef} warning={row.warning} />
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Loading EVF validation data…</div>
          )}
        </Card>

        <div style={{ display: "flex", gap: "var(--space-5)", flexWrap: "wrap" }}>
          {/* Recent Audits */}
          <Card style={{ flex: 2, minWidth: 300 }}>
            <h2 style={{ fontSize: "var(--text-md)", marginBottom: "var(--space-3)", color: "var(--color-text-primary)" }}>Recent Audits</h2>
            {auditsError ? (
              <div style={{ color: "var(--color-critical)", fontSize: "var(--text-sm)" }}>
                ⚠ Could not load audits — you may not have access, or the service is unavailable.
              </div>
            ) : audits.length === 0 ? (
              <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>No audits yet.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: "var(--weight-semibold)" }}>Audit ID</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: "var(--weight-semibold)" }}>Status</th>
                    <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--color-text-secondary)", fontWeight: "var(--weight-semibold)" }}>Risk Score</th>
                  </tr>
                </thead>
                <tbody>
                  {audits.slice(0, 10).map((a) => {
                    // CHUB-003: /api/v1/audits exposes the score as `overall_risk_score`
                    // (AuditListItemOut); `risk_score` is kept only as a defensive fallback.
                    const score = a.overall_risk_score ?? a.risk_score;
                    const auditId = a.audit_id || a.id;
                    const statusTone = a.status === "completed"
                      ? { bg: "var(--color-low-bg)", fg: "var(--color-low)" }
                      : a.status === "failed"
                      ? { bg: "var(--color-critical-bg)", fg: "var(--color-critical)" }
                      : { bg: "var(--color-medium-bg)", fg: "var(--color-medium)" };
                    return (
                      <tr
                        key={auditId}
                        role="button"
                        tabIndex={0}
                        onClick={() => onNavigate?.("trace_view", auditId)}
                        onKeyDown={(e) => { if (e.key === "Enter") onNavigate?.("trace_view", auditId); }}
                        style={{ borderBottom: "1px solid var(--color-border-subtle)", cursor: "pointer" }}
                        title="Open TRACE timeline for this audit"
                      >
                        <td style={{ padding: "8px 8px", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
                          {(a.audit_id || a.id || "").slice(0, 12)}…
                        </td>
                        <td style={{ padding: "8px 8px" }}>
                          <span style={{
                            padding: "2px 8px", borderRadius: "var(--radius-lg)", fontSize: "var(--text-xs)",
                            background: statusTone.bg, color: statusTone.fg,
                          }}>{a.status}</span>
                        </td>
                        <td style={{ padding: "8px 8px", textAlign: "right" }}>
                          {score != null ? <RiskBadge score={score} /> : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Card>

          {/* Readiness Checklist */}
          <Card style={{ flex: 1, minWidth: 240 }}>
            <h2 style={{ fontSize: "var(--text-md)", marginBottom: "var(--space-3)", color: "var(--color-text-primary)" }}>Readiness Checklist</h2>
            {readinessError ? (
              <div style={{ color: "var(--color-critical)", fontSize: "var(--text-sm)" }}>⚠ Could not load readiness checklist.</div>
            ) : !readiness || !Array.isArray(readiness.items) ? (
              <div data-testid="readiness-loading"><Skeleton height={120} /></div>
            ) : (
              <div style={{ fontSize: "var(--text-sm)" }}>
                {readiness.items.map((item) => {
                  const unknown = item.completed === null;
                  const checked = item.completed === true;
                  return (
                    <label
                      key={item.key}
                      title={item.source || undefined}
                      style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10, cursor: item.editable ? "pointer" : "default" }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!item.editable || unknown}
                        onChange={() => toggleReadiness(item)}
                        style={{ marginTop: 2, accentColor: "var(--color-info)" }}
                      />
                      <span style={{ color: checked ? "var(--color-text-muted)" : "var(--color-text-primary)", textDecoration: checked ? "line-through" : "none" }}>
                        {item.label}
                        {!item.editable && <em style={{ color: "var(--color-text-muted)", fontStyle: "normal" }}> · auto</em>}
                        {unknown && <span style={{ color: "var(--color-medium)" }}> · unknown</span>}
                      </span>
                    </label>
                  );
                })}
                <div style={{ marginTop: "var(--space-3)", color: "var(--color-info)", fontWeight: "var(--weight-semibold)", fontSize: "var(--text-sm)" }}>
                  {readiness.items.filter((i) => i.completed === true).length}/{readiness.items.length} complete
                </div>
              </div>
            )}
          </Card>
        </div>

        {/* Compliance Calendar — STORY-010 */}
        <Card style={{ marginTop: "var(--space-5)", marginBottom: 0 }}>
          <h2 style={{ fontSize: "var(--text-md)", marginBottom: "var(--space-4)", color: "var(--color-text-primary)" }}>Compliance Calendar</h2>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-4)" }}>
            QCO expiry dates, next review schedules, and EVF validation tier per framework.
          </p>
          <ComplianceCalendar token={token} />
        </Card>

        {/* Disclaimer */}
        <div style={{ marginTop: "var(--space-6)", padding: "var(--space-3)", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-subtle)", borderRadius: "var(--radius-md)", fontSize: "var(--text-xs)", color: "var(--color-text-secondary)" }}>
          <strong>Disclaimer:</strong> This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification, legal advice, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission.
        </div>
      </div>
    </div>
  );
}
