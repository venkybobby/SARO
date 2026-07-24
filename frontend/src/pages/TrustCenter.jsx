import React, { useEffect, useState } from "react";
import Governance from "./Governance";
import HowSaroReasons from "./HowSaroReasons";
import ClaimsMatrix from "./ClaimsMatrix";
import GovernanceDocs from "./GovernanceDocs";

// STORY-TAB-008 AC-6: latest completed evaluation run as detection-quality
// evidence. Uses the LIST endpoint (TAB-004: admits admin/operator/super_admin
// by account role) and renders ONLY for those roles — other Trust Center
// viewers get no card and no 403. Evidence language only (no pass/fail claim
// beyond the run's own recorded counts).
const EVAL_LIST_ROLES = ["admin", "operator", "super_admin"];

function DetectionQualityCard({ token, user }) {
  const [run, setRun] = useState(null);
  const allowed = EVAL_LIST_ROLES.includes(user?.role);

  useEffect(() => {
    if (!token || !allowed) return;
    fetch("/api/v1/evaluations?status=completed&limit=1", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setRun(Array.isArray(d) && d.length > 0 ? d[0] : null))
      .catch(() => setRun(null));
  }, [token, allowed]);

  if (!allowed || !run) return null;

  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
      padding: "12px 16px", margin: "0 0 16px",
      display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap", fontSize: 13,
    }}>
      <span style={{ fontWeight: 700 }}>Detection quality evidence</span>
      <span style={{ color: "#374151" }}>
        Latest completed evaluation run:
        {run.datasets_passed != null && run.datasets_attempted != null && (
          <> {run.datasets_passed}/{run.datasets_attempted} datasets passed</>
        )}
        {run.total_samples_uploaded != null && <> · {run.total_samples_uploaded.toLocaleString()} samples</>}
        {run.completed_at && <> · {String(run.completed_at).slice(0, 10)}</>}
      </span>
      <span style={{ color: "#9ca3af", fontSize: 11 }}>
        Offline batch evaluation — human review required before acting on any finding.
      </span>
    </div>
  );
}

/**
 * STORY-112: Trust Center consolidates the four previously-separate governance
 * pages (Governance principles, How SARO Reasons, Claims Matrix, DPA & Governance)
 * into one page with internal tabs. Each tab renders the original component
 * unchanged, preserving all content, data sources, and access control.
 *
 * Tab ids match App.jsx's page keys so a redirect of an old key can pass the key
 * straight through as `initialTab`. `initialSection` is forwarded to the Claims
 * Matrix tab to preserve the AIInsights → claims-matrix anchor navigation.
 */
const TABS = [
  { id: "governance", label: "Governance Principles" },
  { id: "how_saro_reasons", label: "How SARO Reasons" },
  { id: "claims_matrix", label: "Claims Matrix" },
  { id: "dpa_governance", label: "DPA & Governance" },
];

export default function TrustCenter({ token, user, initialTab, initialSection }) {
  const [tab, setTab] = useState(
    TABS.some((t) => t.id === initialTab) ? initialTab : "governance"
  );

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <div style={{ padding: "20px 24px 0", fontFamily: "system-ui, sans-serif" }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>🛡️ Trust Center</h1>
        <p style={{ color: "#6b7280", fontSize: 14, margin: "0 0 16px" }}>
          Governance principles, how SARO reasons, the compliance claims matrix, and
          governance documents — consolidated in one place.
        </p>
        <DetectionQualityCard token={token} user={user} />
        <div role="tablist" aria-label="Trust Center sections" style={{ display: "flex", gap: 4, flexWrap: "wrap", borderBottom: "1px solid var(--color-border-subtle, #e5e7eb)" }}>
          {TABS.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                style={{
                  padding: "8px 14px",
                  border: "none",
                  borderBottom: active ? "2px solid #1e40af" : "2px solid transparent",
                  background: "transparent",
                  color: active ? "#1e40af" : "#6b7280",
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      <div role="tabpanel">
        {tab === "governance" && <Governance token={token} />}
        {tab === "how_saro_reasons" && <HowSaroReasons />}
        {tab === "claims_matrix" && <ClaimsMatrix token={token} initialSection={initialSection} />}
        {tab === "dpa_governance" && <GovernanceDocs token={token} />}
      </div>
    </div>
  );
}
