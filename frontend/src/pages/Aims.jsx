/**
 * AIMS — AI Model document lifecycle management (CF-04).
 */
import React, { useEffect, useState } from "react";

export default function Aims({ token, tenantId }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    const url = `/api/v1/aims/models${tenantId ? `?tenant_id=${tenantId}` : ""}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setModels(Array.isArray(d) ? d : d.models || []); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token, tenantId]);

  const STAGE_COLOR = {
    development: "#3b82f6", testing: "#f59e0b", production: "#16a34a",
    deprecated: "#6b7280", retired: "#dc2626",
  };

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📋 AIMS — AI Model Inventory</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        AI Model document lifecycle tracking. Links scan records to document lifecycle stages for ISO 42001 Clause 9 audit evidence.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading model inventory…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}
      {!loading && !error && models.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          No AI models registered in inventory yet. Register models via the API.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
        {models.map((model) => {
          const stage = (model.lifecycle_stage || "development").toLowerCase();
          const color = STAGE_COLOR[stage] || "#6b7280";
          return (
            <div key={model.id || model.model_id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{model.name || model.model_name}</div>
                <span style={{ background: color + "20", color, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                  {stage.toUpperCase()}
                </span>
              </div>
              {model.vendor && <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>Vendor: {model.vendor}</div>}
              {model.version && <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>Version: {model.version}</div>}
              {model.risk_category && (
                <div style={{ fontSize: 12, color: "#374151", marginBottom: 6 }}>Risk Category: {model.risk_category}</div>
              )}
              {model.last_audit_date && (
                <div style={{ fontSize: 11, color: "#9ca3af" }}>Last Audit: {model.last_audit_date.slice(0, 10)}</div>
              )}
              <div style={{ marginTop: 8, fontSize: 11, color: "#64748b", fontStyle: "italic" }}>
                Audit evidence for ISO 42001 document lifecycle review
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
