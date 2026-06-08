/**
 * Admin Settings — user persona assignment and permissions reference.
 */
import React, { useState } from "react";

const PERSONAS = [
  { value: "compliance_lead", label: "⚖️ Compliance Lead" },
  { value: "risk_officer",    label: "📊 Risk Officer" },
  { value: "ai_auditor",      label: "🔍 AI Auditor" },
  { value: "admin",           label: "⚙️ Admin" },
];

const PERMISSIONS_REF = [
  { persona: "⚖️ Compliance Lead", landing: "Compliance Hub",  perms: "TRACE (executive), evidence export, claims matrix, DPA" },
  { persona: "📊 Risk Officer",    landing: "Risk Summary",    perms: "Risk dashboard, vendor risk, IR plan, board PDF" },
  { persona: "🔍 AI Auditor",      landing: "Dashboard",       perms: "TRACE (technical), rule packs, coverage gap, remediation" },
  { persona: "⚙️ Admin",           landing: "Dashboard",       perms: "All tabs and actions" },
];

export default function AdminSettings({ token }) {
  const [userId, setUserId]   = useState("");
  const [persona, setPersona] = useState("compliance_lead");
  const [msg, setMsg]         = useState(null);
  const [loading, setLoading] = useState(false);

  async function assign() {
    if (!userId.trim()) { setMsg({ type: "warn", text: "User UUID is required." }); return; }
    setLoading(true);
    try {
      const r = await fetch(`/api/v1/auth/users/${userId.trim()}/persona?persona_role=${persona}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || r.status);
      }
      setMsg({ type: "ok", text: `Persona '${persona}' assigned to user ${userId.trim()}.` });
      setUserId("");
    } catch (e) {
      setMsg({ type: "err", text: `Failed: ${e.message}` });
    } finally {
      setLoading(false);
    }
  }

  const msgStyle = msg?.type === "ok"
    ? { background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534" }
    : msg?.type === "err"
    ? { background: "#fee2e2", border: "1px solid #fca5a5", color: "#b91c1c" }
    : { background: "#fffbeb", border: "1px solid #fde68a", color: "#92400e" };

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 800 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>⚙️ Admin Settings</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        User management and persona assignment. Personas control which tabs and actions are available.
      </p>

      {/* Persona assignment */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginBottom: 20 }}>
        <h2 style={{ fontSize: 15, marginBottom: 4 }}>👤 User Persona Assignment</h2>
        <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
          Assign a persona role to any user. Personas control which tabs and actions are available.
        </p>

        {msg && (
          <div style={{ ...msgStyle, padding: "10px 14px", borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
            {msg.text}
          </div>
        )}

        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>User UUID</label>
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6"
              style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, boxSizing: "border-box" }}
            />
          </div>
          <div style={{ minWidth: 200 }}>
            <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Persona Role</label>
            <select
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
            >
              {PERSONAS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
        </div>
        <button
          onClick={assign}
          disabled={loading}
          style={{ padding: "10px 20px", background: "#0d9488", color: "#fff", border: "none", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer" }}
        >
          {loading ? "Assigning…" : "Assign Persona"}
        </button>
      </div>

      {/* Permissions reference */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb", fontWeight: 700, fontSize: 14 }}>
          🔑 Persona Permissions Reference
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Persona</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Default Landing</th>
              <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Key Permissions</th>
            </tr>
          </thead>
          <tbody>
            {PERMISSIONS_REF.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "10px 12px", fontWeight: 600 }}>{row.persona}</td>
                <td style={{ padding: "10px 12px", color: "#6b7280" }}>{row.landing}</td>
                <td style={{ padding: "10px 12px", color: "#374151" }}>{row.perms}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
