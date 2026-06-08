/**
 * Demo Requests — admin view of demo signup requests with status management.
 */
import React, { useEffect, useState } from "react";

const STATUSES = ["pending", "contacted", "converted", "rejected"];
const STATUS_BADGE = {
  pending:   { bg: "#fef3c7", color: "#92400e", icon: "🟡" },
  contacted: { bg: "#d1fae5", color: "#065f46", icon: "🟢" },
  converted: { bg: "#d1fae5", color: "#065f46", icon: "✅" },
  rejected:  { bg: "#fee2e2", color: "#991b1b", icon: "🔴" },
};

export default function DemoRequests({ token }) {
  const [requests, setRequests] = useState([]);
  const [filter, setFilter]     = useState("All");
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [updating, setUpdating] = useState({});

  async function load(status) {
    setLoading(true);
    const qs = status && status !== "All" ? `?status=${status}` : "";
    try {
      const r = await fetch(`/api/v1/demo/requests${qs}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(r.status);
      setRequests(await r.json());
      setError(null);
    } catch (e) {
      setError(`Failed to load demo requests (${e.message})`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token) load(filter); }, [token, filter]);

  async function updateStatus(id, newStatus) {
    setUpdating((u) => ({ ...u, [id]: true }));
    try {
      const r = await fetch(`/api/v1/demo/requests/${id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!r.ok) throw new Error(r.status);
      await load(filter);
    } catch {
    } finally {
      setUpdating((u) => ({ ...u, [id]: false }));
    }
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", maxWidth: 1000 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>📋 Demo Requests</h1>
      <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 16 }}>
        Manage inbound demo signup requests.
      </p>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <label style={{ fontSize: 13, fontWeight: 600 }}>Filter by status:</label>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13 }}
        >
          <option>All</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <span style={{ fontSize: 13, color: "#6b7280" }}>{requests.length} result{requests.length !== 1 ? "s" : ""}</span>
      </div>

      {loading && <div style={{ color: "#9ca3af" }}>Loading…</div>}
      {error && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}
      {!loading && !error && requests.length === 0 && (
        <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: 24, textAlign: "center", color: "#9ca3af" }}>
          No requests match the selected filter.
        </div>
      )}

      {requests.map((req) => {
        const badge = STATUS_BADGE[req.status] || STATUS_BADGE.pending;
        return (
          <div key={req.id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{req.first_name} {req.last_name}</span>
                  <span style={{ fontSize: 13, color: "#6b7280" }}>{req.email}</span>
                  <span style={{ background: badge.bg, color: badge.color, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    {badge.icon} {req.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: req.message ? 8 : 0 }}>
                  {req.company_name && <span>Company: {req.company_name}</span>}
                  {req.contact_number && <span style={{ marginLeft: 12 }}>Phone: {req.contact_number}</span>}
                  {req.created_at && <span style={{ marginLeft: 12 }}>Submitted: {req.created_at.slice(0, 10)}</span>}
                </div>
                {req.message && (
                  <div style={{ fontSize: 13, color: "#374151", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: 8 }}>
                    {req.message}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 130 }}>
                <select
                  defaultValue={req.status}
                  onChange={(e) => updateStatus(req.id, e.target.value)}
                  disabled={updating[req.id]}
                  style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 12 }}
                >
                  {STATUSES.map((s) => <option key={s}>{s}</option>)}
                </select>
                {updating[req.id] && <span style={{ fontSize: 11, color: "#9ca3af" }}>Updating…</span>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
