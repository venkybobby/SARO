/**
 * LiveFeed — real-time audit list from GET /api/v1/audits.
 * Polls every 5 seconds. No hardcoded data.
 */
import React, { useEffect, useState } from "react";
import { fetchRecentAudits } from "../api/saro";

export default function LiveFeed({ token, tenantId }) {
  const [audits, setAudits] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    const load = async () => {
      try {
        const data = await fetchRecentAudits(token, tenantId);
        setAudits(Array.isArray(data) ? data : data.items || []);
        setError(null);
      } catch (e) {
        setError(e.message);
      }
    };
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [token, tenantId]);

  if (error) return <div style={{ color: "#dc2626" }}>⚠ {error}</div>;
  if (!audits.length) return <div style={{ color: "#9ca3af" }}>No audits yet</div>;

  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {audits.slice(0, 10).map((a) => (
        <li key={a.audit_id || a.id} style={{ padding: "6px 0", borderBottom: "1px solid #f3f4f6" }}>
          <span style={{ fontFamily: "monospace", fontSize: 12 }}>
            {(a.audit_id || a.id || "").slice(0, 8)}…
          </span>{" "}
          <span
            style={{
              marginLeft: 8,
              padding: "2px 8px",
              borderRadius: 12,
              fontSize: 11,
              background:
                a.status === "completed" ? "#d1fae5" :
                a.status === "failed"    ? "#fee2e2" : "#fef3c7",
              color:
                a.status === "completed" ? "#065f46" :
                a.status === "failed"    ? "#991b1b" : "#92400e",
            }}
          >
            {a.status}
          </span>
          {a.risk_score != null && (
            <span style={{ marginLeft: 8, fontSize: 12, color: "#6b7280" }}>
              risk: {(a.risk_score * 100).toFixed(0)}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
