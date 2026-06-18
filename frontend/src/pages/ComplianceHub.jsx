/**
 * Compliance Hub — landing page for compliance_lead persona.
 * Sections: EVF Validation Status, Recent Audits, Governance Docs, QCO Expiry Alerts, Readiness Checklist.
 */
import React, { useEffect, useState } from "react";
import { Skeleton } from "../components/ui/index.jsx";

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

function TierBadge({ tier, label, qcoRef, warning }) {
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
  const color = s >= 70 ? "#dc2626" : s >= 40 ? "#ca8a04" : "#16a34a";
  return (
    <span style={{ background: color + "20", color, border: `1px solid ${color}40`, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
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

  if (loading) return <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading calendar…</div>;

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
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
            <th style={{ textAlign: "left", padding: "8px 10px", color: "#6b7280", fontWeight: 600 }}>Framework</th>
            <th style={{ textAlign: "left", padding: "8px 10px", color: "#6b7280", fontWeight: 600 }}>EVF Tier</th>
            <th style={{ textAlign: "left", padding: "8px 10px", color: "#6b7280", fontWeight: 600 }}>QCO Expiry</th>
            <th style={{ textAlign: "left", padding: "8px 10px", color: "#6b7280", fontWeight: 600 }}>Next Review</th>
            <th style={{ textAlign: "left", padding: "8px 10px", color: "#6b7280", fontWeight: 600 }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ fw, label, tier, expDate, revDate, days }) => {
            const tierCfg = TIER_CONFIG[tier] || { color: "#64748b", icon: "🔒", short: "INTERNAL ONLY" };
            const urgentColor = days !== null && days < 30 ? "#dc2626" : days !== null && days < 60 ? "#ca8a04" : "#374151";
            return (
              <tr key={fw} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "10px 10px", fontWeight: 600 }}>{label}</td>
                <td style={{ padding: "10px 10px" }}>
                  <span style={{
                    background: tierCfg.color + "20", color: tierCfg.color,
                    border: `1px solid ${tierCfg.color}40`,
                    padding: "2px 7px", borderRadius: 10, fontSize: 11, fontWeight: 700,
                  }}>
                    {tierCfg.icon} {tierCfg.short}
                  </span>
                </td>
                <td style={{ padding: "10px 10px", color: urgentColor, fontFamily: "monospace", fontSize: 12 }}>
                  {expDate
                    ? `${expDate.slice(0, 10)}${days !== null ? ` (${days > 0 ? `${days}d` : "EXPIRED"})` : ""}`
                    : <span style={{ color: "#9ca3af" }}>—</span>}
                </td>
                <td style={{ padding: "10px 10px", fontFamily: "monospace", fontSize: 12, color: "#6b7280" }}>
                  {revDate ? revDate.slice(0, 10) : <span style={{ color: "#9ca3af" }}>—</span>}
                </td>
                <td style={{ padding: "10px 10px" }}>
                  {days !== null && days < 0
                    ? <span style={{ color: "#dc2626", fontWeight: 700, fontSize: 11 }}>⚠ EXPIRED</span>
                    : days !== null && days < 30
                    ? <span style={{ color: "#dc2626", fontWeight: 600, fontSize: 11 }}>🔴 Urgent</span>
                    : days !== null && days < 60
                    ? <span style={{ color: "#ca8a04", fontWeight: 600, fontSize: 11 }}>🟡 Due soon</span>
                    : tier === "tier_3"
                    ? <span style={{ color: "#64748b", fontSize: 11 }}>Not assessed</span>
                    : <span style={{ color: "#16a34a", fontSize: 11 }}>✓ OK</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {expiries.length === 0 && statuses.length === 0 && (
        <div style={{ color: "#9ca3af", fontSize: 12, marginTop: 8, fontStyle: "italic" }}>
          No EVF records found — all frameworks are at Tier 3 (Internal Review Only).
        </div>
      )}
      <p style={{ fontSize: 11, color: "#9ca3af", marginTop: 10 }}>
        EVF = External Validation Framework · QCO = Qualified Compliance Opinion.
        Expiry data requires a QCO reference number from an approved SME firm.
      </p>
    </div>
  );
}

export default function ComplianceHub({ token, tenantId }) {
  const [coverage, setCoverage] = useState(null);
  const [audits, setAudits] = useState([]);
  const [checks, setChecks] = useState(CHECKLIST.map(() => false));
  const [error, setError] = useState(null);
  const [statuses, setStatuses] = useState([]);
  const [tierUnavailable, setTierUnavailable] = useState(false);
  const [auditsError, setAuditsError] = useState(false);

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
  }, [token, tenantId]);

  const evfRows = buildEvfRows({ coverage, statuses, tierUnavailable });

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1200 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🏛️ Compliance Hub</h1>
      <p style={{ color: "#6b7280", marginBottom: 24, fontSize: 14 }}>
        EVF validation status, recent audits, and readiness tracking for compliance leads.
      </p>

      {/* CHUB-005: overall matrix-coverage headline + provenance */}
      <Card style={{ marginBottom: 20 }}>
        {error ? (
          <div>
            <div style={{ fontSize: 30, fontWeight: 700, color: "#374151" }}>—</div>
            <div style={{ color: "#dc2626", fontSize: 13 }}>⚠ {error}</div>
          </div>
        ) : coverage == null ? (
          <div data-testid="coverage-headline-loading">
            <Skeleton width={220} height={34} />
            <div style={{ marginTop: 8 }}><Skeleton width={320} height={14} /></div>
          </div>
        ) : coverage.total_rules === 0 ? (
          <div style={{ color: "#6b7280", fontSize: 15 }}>No matrix data yet</div>
        ) : (
          <div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ fontSize: 30, fontWeight: 700, color: "#0d9488" }}>
                {coverage.overall_coverage_pct}%
              </span>
              <span style={{ fontSize: 14, color: "#374151", fontWeight: 600 }}>Matrix coverage</span>
            </div>
            <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
              {coverage.framework_count} frameworks · {coverage.total_rules} rules
            </div>
            <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>
              as of {mostRecentLastUpdated(coverage.frameworks) || "—"}
            </div>
          </div>
        )}
      </Card>

      {/* EVF Validation Status */}
      <Card style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 16 }}>EVF Validation Status</h2>
        {error && <div style={{ color: "#dc2626", marginBottom: 12, fontSize: 13 }}>⚠ {error}</div>}
        {tierUnavailable && (
          <div style={{ color: "#ca8a04", marginBottom: 12, fontSize: 12 }}>
            ⚠ Validation status unavailable — treated as internal only.
          </div>
        )}
        {coverage?.frameworks || evfRows.length > 0 ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {evfRows.map((row) => (
              <div key={row.key} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{row.label}</span>
                  {row.coveragePct != null && (
                    <span style={{ fontSize: 13, color: "#0d9488" }}>{row.coveragePct.toFixed(1)}%</span>
                  )}
                </div>
                {row.coveragePct != null && (
                  <div style={{ height: 4, background: "#e5e7eb", borderRadius: 2, marginBottom: 8 }}>
                    <div style={{ height: 4, width: `${row.coveragePct}%`, background: "#0d9488", borderRadius: 2 }} />
                  </div>
                )}
                {/* Invariant: every row renders a tier badge — never a coverage % alone. */}
                <TierBadge tier={row.tier} label={row.tierLabel} qcoRef={row.qcoRef} warning={row.warning} />
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
          {auditsError ? (
            <div style={{ color: "#dc2626", fontSize: 13 }}>
              ⚠ Could not load audits — you may not have access, or the service is unavailable.
            </div>
          ) : audits.length === 0 ? (
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
                {audits.slice(0, 10).map((a) => {
                  // CHUB-003: /api/v1/audits exposes the score as `overall_risk_score`
                  // (AuditListItemOut); `risk_score` is kept only as a defensive fallback.
                  const score = a.overall_risk_score ?? a.risk_score;
                  return (
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

      {/* Compliance Calendar — STORY-010 */}
      <Card style={{ marginTop: 20, marginBottom: 0 }}>
        <h2 style={{ fontSize: 15, marginBottom: 14 }}>📅 Compliance Calendar</h2>
        <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 14 }}>
          QCO expiry dates, next review schedules, and EVF validation tier per framework.
        </p>
        <ComplianceCalendar token={token} />
      </Card>

      {/* Disclaimer */}
      <div style={{ marginTop: 24, padding: 12, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: 11, color: "#64748b" }}>
        <strong>Disclaimer:</strong> This report is audit evidence generated by SARO v8.0.0. It does not constitute regulatory certification, legal advice, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission.
      </div>
    </div>
  );
}
