import React, { useState } from "react";
import Governance from "./Governance";
import HowSaroReasons from "./HowSaroReasons";
import ClaimsMatrix from "./ClaimsMatrix";
import GovernanceDocs from "./GovernanceDocs";

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

export default function TrustCenter({ token, initialTab, initialSection }) {
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
