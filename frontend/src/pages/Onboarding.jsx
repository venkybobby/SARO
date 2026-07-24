/**
 * Onboarding — client/tenant onboarding checklist.
 *
 * STORY-TAB-002: renders the backend checklist verbatim (routers/onboarding.py):
 *   GET /api/v1/onboarding/status →
 *     {tenant_id, completed_steps, total_steps, completion_pct,
 *      onboarding_complete, steps:[{key,label,completed,cta_url}]}
 * Progress always derives from the API fields; steps are data-driven so
 * future backend keys render without a frontend change.
 */
import React, { useEffect, useState } from "react";
import { ONBOARDING_STEP_NAV } from "../config/onboardingNav.js";

export default function Onboarding({ token, tenantId, onNavigate }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    if (!token) return;
    const url = `/api/v1/onboarding/status${tenantId ? `?tenant_id=${tenantId}` : ""}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((d) => { setData(d); setError(null); setLoading(false); })
      .catch((e) => { setError(`${e}`); setLoading(false); });
  }, [token, tenantId]);

  const steps = data?.steps || [];
  const pct = data?.completion_pct ?? 0;

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 800 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🏢 Onboarding</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Track your SARO setup progress. Complete all steps to be fully operational.
      </p>

      {loading && <div style={{ color: "#9ca3af" }}>Loading onboarding status…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ Failed to load onboarding status ({error})
        </div>
      )}

      {!loading && !error && steps.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          No onboarding steps configured for this tenant.
        </div>
      )}

      {!loading && !error && steps.length > 0 && (
        <>
          {/* Progress bar — API-computed, never recomputed locally */}
          <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>Setup Progress</span>
              <span style={{ fontWeight: 700, fontSize: 14, color: "#0d9488" }}>{pct}%</span>
            </div>
            <div style={{ height: 8, background: "#e5e7eb", borderRadius: 4 }}>
              <div style={{ height: 8, width: `${pct}%`, background: "#0d9488", borderRadius: 4, transition: "width 0.5s" }} />
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: "#9ca3af" }}>
              {data.completed_steps}/{data.total_steps} steps complete
            </div>
          </div>

          {/* Steps — rendered from the API, label-driven */}
          {steps.map((step) => {
            const done = !!step.completed;
            const navTarget = ONBOARDING_STEP_NAV[step.key];
            return (
              <div key={step.key} style={{
                display: "flex", alignItems: "center", gap: 14, padding: 16,
                background: "#fff", border: `1px solid ${done ? "#bbf7d0" : "#e5e7eb"}`,
                borderRadius: 8, marginBottom: 8,
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                  background: done ? "#0d9488" : "#f3f4f6",
                  color: done ? "#fff" : "#9ca3af",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 700, fontSize: 14,
                }}>
                  {done ? "✓" : "○"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: done ? "#065f46" : "#374151" }}>
                    {step.label}
                  </div>
                </div>
                {!done && navTarget && onNavigate && (
                  <button
                    onClick={() => onNavigate(navTarget)}
                    style={{
                      padding: "5px 12px", background: "#f0fdf4", color: "#0d9488",
                      border: "1px solid #bbf7d0", borderRadius: 6,
                      cursor: "pointer", fontSize: 12, fontWeight: 600,
                    }}
                  >
                    Go →
                  </button>
                )}
              </div>
            );
          })}

          {data.onboarding_complete && (
            <div style={{ marginTop: 16, background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 20, textAlign: "center", color: "#166534" }}>
              🎉 <strong>Onboarding complete!</strong> Your SARO instance is fully configured and operational.
            </div>
          )}
        </>
      )}
    </div>
  );
}
