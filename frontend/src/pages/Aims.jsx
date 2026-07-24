/**
 * AIMS — AI Model document lifecycle registry (ISO 42001 evidence surface).
 *
 * STORY-TAB-007: renders ONLY the fields the API stores (routers/aims.py):
 *   {model_id, name, version, effective_date, owner_email,
 *    linked_audit_count, created_at}
 * No fabricated stage/tier badges — a lifecycle badge renders only if the API
 * ever returns a stored `lifecycle_stage` (none exists today).
 */
import React, { useEffect, useState } from "react";

const STAGE_COLOR = {
  development: "#3b82f6", testing: "#f59e0b", production: "#16a34a",
  deprecated: "#6b7280", retired: "#dc2626",
};

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

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📋 AIMS — AI Model Inventory</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        AI Model document lifecycle tracking. Links scan records to document lifecycle stages for ISO 42001 Clause 9 audit evidence.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading model inventory…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ Failed to load model inventory ({error})
        </div>
      )}
      {!loading && !error && models.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          No AI models registered in inventory yet. Register one by creating an AIMS
          document (POST /api/v1/aims/documents) or from the Compliance Hub evidence workflow.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
        {models.map((model) => {
          // A stage badge renders ONLY from stored data — never a default.
          const stage = model.lifecycle_stage ? String(model.lifecycle_stage).toLowerCase() : null;
          const stageColor = stage ? (STAGE_COLOR[stage] || "#6b7280") : null;
          return (
            <div key={model.model_id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8, gap: 8 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{model.name}</div>
                {stage && (
                  <span style={{ background: stageColor + "20", color: stageColor, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    {stage.toUpperCase()}
                  </span>
                )}
              </div>
              {model.version && <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>Version: {model.version}</div>}
              {model.owner_email && <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>Owner: {model.owner_email}</div>}
              {model.effective_date && (
                <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>Effective: {model.effective_date.slice(0, 10)}</div>
              )}
              <div style={{ fontSize: 12, color: "#374151", marginBottom: 6 }}>
                {model.linked_audit_count ?? 0} linked audit{model.linked_audit_count === 1 ? "" : "s"}
              </div>
              {Array.isArray(model.framework_coverage) && model.framework_coverage.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                  {model.framework_coverage.map((fw) => (
                    <span key={fw} style={{ background: "#eff6ff", color: "#1d4ed8", padding: "1px 8px", borderRadius: 10, fontSize: 11, fontWeight: 600 }}>
                      {fw}
                    </span>
                  ))}
                </div>
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
