/**
 * Remediation — view and manage open remediation actions.
 */
import React, { useEffect, useState } from "react";

export default function Remediation({ token, tenantId }) {
  const [items, setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [updating, setUpdating] = useState({});

  async function load() {
    setLoading(true);
    try {
      const r = await fetch(
        `/api/v1/remediation${tenantId ? `?tenant_id=${tenantId}` : ""}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      setItems(Array.isArray(d) ? d : d.items || []);
      setError(null);
    } catch (e) {
      setError(`Failed to load remediations (${e.message})`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token) load(); }, [token, tenantId]);

  async function markComplete(id) {
    setUpdating((u) => ({ ...u, [id]: true }));
    try {
      await fetch(`/api/v1/remediation/${id}/complete`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      await load();
    } catch {
    } finally {
      setUpdating((u) => ({ ...u, [id]: false }));
    }
  }

  const SEV_COLOR = { critical: "#dc2626", high: "#ea580c", medium: "#ca8a04", low: "#16a34a" };

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🔧 Remediation</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Open remediation actions requiring human review and sign-off.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 20, textAlign: "center", color: "#166534" }}>
          ✓ No open remediation actions — all findings have been addressed.
        </div>
      )}

      {items.map((item) => {
        const sev = (item.severity || "medium").toLowerCase();
        const color = SEV_COLOR[sev] || "#6b7280";
        return (
          <div key={item.id || item.remediation_id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ background: color + "20", color, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    {sev.toUpperCase()}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>
                    {item.title || item.rule_id || "Remediation Action"}
                  </span>
                </div>
                {item.description && (
                  <p style={{ fontSize: 13, color: "#374151", margin: "0 0 8px" }}>{item.description}</p>
                )}
                {item.guidance && (
                  <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: 10, fontSize: 13, color: "#374151", marginBottom: 8 }}>
                    <strong>Guidance:</strong> {item.guidance}
                  </div>
                )}
                {item.effort_estimate && (
                  <div style={{ fontSize: 12, color: "#9ca3af" }}>Effort: {item.effort_estimate}</div>
                )}
              </div>
              <div>
                <button
                  onClick={() => markComplete(item.id || item.remediation_id)}
                  disabled={updating[item.id || item.remediation_id]}
                  style={{ padding: "6px 14px", background: "#0d9488", color: "#fff", border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer" }}
                >
                  {updating[item.id || item.remediation_id] ? "…" : "Mark Complete"}
                </button>
              </div>
            </div>
          </div>
        );
      })}

      <div style={{ marginTop: 16, fontSize: 11, color: "#9ca3af" }}>
        Recommended remediation — human validation required before sign-off.
      </div>
    </div>
  );
}
