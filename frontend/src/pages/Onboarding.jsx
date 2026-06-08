/**
 * Onboarding — client/tenant onboarding checklist and setup wizard.
 */
import React, { useEffect, useState } from "react";

const ONBOARDING_STEPS = [
  { id: "tenant_created",    label: "Tenant Created",           desc: "Organisation account created in SARO." },
  { id: "users_invited",     label: "Users Invited",            desc: "Team members have been sent login invitations." },
  { id: "personas_assigned", label: "Personas Assigned",        desc: "Each user has been assigned a persona role." },
  { id: "first_scan",        label: "First Scan Completed",     desc: "At least one AI output has been scanned." },
  { id: "rule_packs_reviewed",label: "Rule Packs Reviewed",     desc: "Applicable rule packs selected for your vertical." },
  { id: "integrations",      label: "Integrations Configured",  desc: "GitHub / CI connectors configured." },
  { id: "compliance_review", label: "Compliance Review Booked", desc: "Initial compliance review call scheduled." },
];

export default function Onboarding({ token, tenantId }) {
  const [progress, setProgress] = useState({});
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    if (!token) return;
    const url = `/api/v1/onboarding/status${tenantId ? `?tenant_id=${tenantId}` : ""}`;
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : {})
      .then((d) => { setProgress(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token, tenantId]);

  const completed = ONBOARDING_STEPS.filter((s) => progress[s.id]).length;
  const pct = Math.round((completed / ONBOARDING_STEPS.length) * 100);

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 800 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>🏢 Onboarding</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Track your SARO setup progress. Complete all steps to be fully operational.
      </p>

      {/* Progress bar */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Setup Progress</span>
          <span style={{ fontWeight: 700, fontSize: 14, color: "#0d9488" }}>{pct}%</span>
        </div>
        <div style={{ height: 8, background: "#e5e7eb", borderRadius: 4 }}>
          <div style={{ height: 8, width: `${pct}%`, background: "#0d9488", borderRadius: 4, transition: "width 0.5s" }} />
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: "#9ca3af" }}>
          {completed}/{ONBOARDING_STEPS.length} steps complete
        </div>
      </div>

      {/* Steps */}
      {ONBOARDING_STEPS.map((step) => {
        const done = !!progress[step.id];
        return (
          <div key={step.id} style={{
            display: "flex", alignItems: "flex-start", gap: 14, padding: 16,
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
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, color: done ? "#065f46" : "#374151" }}>
                {step.label}
              </div>
              <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>{step.desc}</div>
            </div>
          </div>
        );
      })}

      {pct === 100 && (
        <div style={{ marginTop: 16, background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 20, textAlign: "center", color: "#166534" }}>
          🎉 <strong>Onboarding complete!</strong> Your SARO instance is fully configured and operational.
        </div>
      )}
    </div>
  );
}
