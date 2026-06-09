import React, { useEffect, useState } from "react";

const PERSONAS = [
  { value: "compliance_lead", label: "Compliance Lead" },
  { value: "risk_officer",    label: "Risk Officer" },
  { value: "ai_auditor",      label: "AI Auditor" },
  { value: "admin",           label: "Admin" },
  { value: "super_admin",     label: "Super Admin" },
  { value: "operator",        label: "Operator" },
];

const PERMISSIONS_REF = [
  { persona: "Compliance Lead", landing: "Compliance Hub",  perms: "TRACE (executive), evidence export, claims matrix, DPA" },
  { persona: "Risk Officer",    landing: "Risk Summary",    perms: "Risk dashboard, trace view, AI insights, reports" },
  { persona: "AI Auditor",      landing: "Dashboard",       perms: "TRACE (technical), rule packs, coverage gap, remediation" },
  { persona: "Admin",           landing: "Dashboard",       perms: "All tabs and actions" },
  { persona: "Super Admin",     landing: "Dashboard",       perms: "All tabs except EVF admin and demo requests" },
  { persona: "Operator",        landing: "Dashboard",       perms: "Dashboard, upload, trace view, remediation" },
];

export default function AdminSettings({ token }) {
  const [users,      setUsers]      = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [search,     setSearch]     = useState("");
  const [assigning,  setAssigning]  = useState(null); // user id being assigned
  const [pendingPersona, setPendingPersona] = useState({});
  const [msg,        setMsg]        = useState(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch("/api/v1/auth/users", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error(`${r.status}`);
        setUsers(await r.json());
      } catch (e) {
        setError(`Failed to load users: ${e.message}`);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  async function assignPersona(userId, persona) {
    setAssigning(userId);
    setMsg(null);
    try {
      const r = await fetch(`/api/v1/auth/users/${userId}/persona?persona_role=${persona}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || r.status);
      }
      const updated = await r.json();
      setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, persona_role: updated.persona_role } : u));
      setPendingPersona((prev) => { const n = { ...prev }; delete n[userId]; return n; });
      setMsg({ type: "ok", text: `Persona updated for ${updated.email}` });
    } catch (e) {
      setMsg({ type: "err", text: `Failed: ${e.message}` });
    } finally {
      setAssigning(null);
    }
  }

  const filtered = users.filter((u) =>
    !search || u.email.toLowerCase().includes(search.toLowerCase())
  );

  const msgStyle = msg?.type === "ok"
    ? { background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534" }
    : { background: "#fee2e2", border: "1px solid #fca5a5", color: "#b91c1c" };

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 900 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>Admin Settings</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20 }}>
        Manage user personas. Personas control which tabs and actions are available to each user.
      </p>

      {msg && (
        <div style={{ ...msgStyle, padding: "10px 14px", borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
          {msg.text}
        </div>
      )}

      {/* User list */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 24 }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontWeight: 700, fontSize: 14, flex: 1 }}>Users</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by email…"
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, width: 220 }}
          />
        </div>

        {loading ? (
          <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", fontSize: 13 }}>Loading users…</div>
        ) : error ? (
          <div style={{ padding: 24, color: "#b91c1c", fontSize: 13 }}>{error}</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", fontSize: 13 }}>No users found.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f8fafc" }}>
                <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Email</th>
                <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Current Persona</th>
                <th style={{ textAlign: "left", padding: "10px 12px", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb" }}>Change Persona</th>
                <th style={{ width: 100, padding: "10px 12px", borderBottom: "1px solid #e5e7eb" }} />
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const pending = pendingPersona[u.id] ?? u.persona_role ?? u.role ?? "operator";
                const changed = pending !== (u.persona_role ?? u.role);
                return (
                  <tr key={u.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "10px 12px", color: "#111827" }}>{u.email}</td>
                    <td style={{ padding: "10px 12px", color: "#6b7280", fontFamily: "monospace", fontSize: 12 }}>
                      {u.persona_role || u.role || "—"}
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <select
                        value={pending}
                        onChange={(e) => setPendingPersona((prev) => ({ ...prev, [u.id]: e.target.value }))}
                        style={{ padding: "5px 8px", borderRadius: 5, border: "1px solid #d1d5db", fontSize: 13 }}
                      >
                        {PERSONAS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: "8px 12px", textAlign: "right" }}>
                      <button
                        disabled={!changed || assigning === u.id}
                        onClick={() => assignPersona(u.id, pending)}
                        style={{
                          padding: "5px 12px", borderRadius: 5, fontSize: 12, fontWeight: 600,
                          background: changed ? "#0d9488" : "#e5e7eb",
                          color: changed ? "#fff" : "#9ca3af",
                          border: "none", cursor: changed ? "pointer" : "default",
                        }}
                      >
                        {assigning === u.id ? "Saving…" : "Save"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Permissions reference */}
      <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #e5e7eb", fontWeight: 700, fontSize: 14 }}>
          Persona Permissions Reference
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
