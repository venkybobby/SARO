/**
 * EVF Admin Status — SAR-004, admin-only EVF validation management.
 */
import React, { useEffect, useState } from "react";

const TIER_CONFIG = {
  tier_1: { color: "#16a34a", icon: "✅", label: "Externally Reviewed — QCO Issued" },
  tier_2: { color: "#ca8a04", icon: "⏳", label: "Under Active SME Review" },
  tier_3: { color: "#64748b", icon: "🔒", label: "Internal Only — Not for External Claim" },
};

export default function EvfAdmin({ token }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    fetch("/api/v1/evf/status", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token]);

  const frameworks = data?.frameworks || [];

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 900 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🔐 EVF Status</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 4 }}>
        External SME Validation Framework — admin view of QCO issuance status across all frameworks.
      </p>
      <div style={{ background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 6, padding: "10px 14px", marginBottom: 20, fontSize: 13, color: "#92400e" }}>
        ⚠ <strong>Sales instruction P-0:</strong> No new external compliance claims for any framework until a QCO reference number is assigned. Use Tier 3 language in all external materials.
      </div>

      {loading && <div style={{ color: "#9ca3af" }}>Loading EVF status…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {frameworks.length > 0 ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {frameworks.map((fw) => {
            const cfg = TIER_CONFIG[fw.evf_tier] || TIER_CONFIG.tier_3;
            return (
              <div key={fw.framework} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>{fw.display_name || fw.framework}</div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ background: cfg.color + "20", color: cfg.color, padding: "3px 10px", borderRadius: 10, fontSize: 12, fontWeight: 700 }}>
                    {cfg.icon} {fw.evf_tier?.replace("_", " ").toUpperCase() || "TIER 3"}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#374151", marginBottom: 6 }}>{cfg.label}</div>
                {fw.scope && (
                  <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 6 }}>Scope: {fw.scope}</div>
                )}
                {fw.evf_qco_reference && (
                  <div style={{ fontFamily: "monospace", fontSize: 11, color: "#0d9488" }}>QCO: {fw.evf_qco_reference}</div>
                )}
                {fw.qco_expiry && (
                  <div style={{ fontSize: 11, color: "#9ca3af" }}>Expiry: {fw.qco_expiry}</div>
                )}
              </div>
            );
          })}
        </div>
      ) : !loading && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24 }}>
          <h2 style={{ fontSize: 15, marginBottom: 12 }}>Default EVF Status</h2>
          <p style={{ fontSize: 13, color: "#374151", marginBottom: 16 }}>
            No frameworks have completed External SME Validation. All are in <strong>Internal Review Only (Tier 3)</strong> state as of 2026-06-02.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {["EU AI Act", "NIST AI RMF 1.0", "AIGP", "ISO 42001"].map((fw) => (
              <div key={fw} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{fw}</div>
                <span style={{ background: "#f1f5f9", color: "#64748b", padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                  🔒 Internal Review Only
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
