/**
 * Remediation — view and manage open remediation actions.
 *
 * STORY-TAB-001: consumes the real backend contract (routers/remediation.py):
 *   GET   /api/v1/remediation                        → {traces:[...], total, page, page_size, pages}
 *   PATCH /api/v1/remediation/traces/{id}/remediate  ← {remediation_note} (note is required; 422 if blank)
 */
import React, { useEffect, useState } from "react";

// The API reports the trace `result`, not a severity; color only groups it.
const RESULT_COLOR = { fail: "#dc2626", warn: "#ca8a04" };

export default function Remediation({ token, tenantId }) {
  const [traces, setTraces] = useState([]);
  const [total, setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [noteFor, setNoteFor] = useState(null);   // trace id whose note input is open
  const [noteText, setNoteText] = useState("");
  const [updating, setUpdating] = useState(false);
  const [actionError, setActionError] = useState(null);

  async function load() {
    setLoading(true);
    setNoteFor(null);
    setActionError(null);
    try {
      const r = await fetch(
        `/api/v1/remediation${tenantId ? `?tenant_id=${tenantId}` : ""}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      setTraces(Array.isArray(d.traces) ? d.traces : []);
      setTotal(typeof d.total === "number" ? d.total : 0);
      setError(null);
    } catch (e) {
      setError(`Failed to load remediations (${e.message})`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token) load(); }, [token, tenantId]); // eslint-disable-line react-hooks/exhaustive-deps

  function openNote(id) {
    setNoteFor(id);
    setNoteText("");
    setActionError(null);
  }

  async function markRemediated(id) {
    if (updating) return; // double-click before re-render must not double-PATCH
    const note = noteText.trim();
    if (!note) return; // backend 422s on a blank note — don't send it
    setUpdating(true);
    setActionError(null);
    try {
      const r = await fetch(`/api/v1/remediation/traces/${id}/remediate`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ remediation_note: note }),
      });
      if (!r.ok) throw new Error(r.status);
      setNoteFor(null);
      setNoteText("");
      await load();
    } catch (e) {
      setActionError(`Failed to mark as remediated (${e.message})`);
    } finally {
      setUpdating(false);
    }
  }

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
      {actionError && (
        <div style={{ background: "#fee2e2", border: "1px solid #fca5a5", borderRadius: 8, padding: "12px 16px", color: "#b91c1c", fontSize: 13, marginBottom: 12 }}>
          ⚠ {actionError}
        </div>
      )}

      {!loading && !error && traces.length === 0 && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 20, textAlign: "center", color: "#166534" }}>
          ✓ No open remediation actions — all findings have been addressed.
        </div>
      )}

      {!loading && !error && total > traces.length && (
        <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 10 }}>
          Showing {traces.length} of {total} open items
        </div>
      )}

      {traces.map((t) => {
        const result = (t.result || "").toLowerCase();
        const color = RESULT_COLOR[result] || "#6b7280";
        const noteOpen = noteFor === t.id;
        return (
          <div key={t.id} style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                  <span style={{ background: color + "20", color, padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 700 }}>
                    {(t.result || "open").toUpperCase()}
                  </span>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>
                    {t.check_name || "Remediation Action"}
                  </span>
                  {t.gate_name && (
                    <span style={{ fontSize: 12, color: "#9ca3af" }}>{t.gate_name}</span>
                  )}
                </div>
                {t.reason && (
                  <p style={{ fontSize: 13, color: "#374151", margin: "0 0 8px" }}>{t.reason}</p>
                )}
                {t.remediation_hint && (
                  <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: 10, fontSize: 13, color: "#374151", marginBottom: 8 }}>
                    <strong>Guidance:</strong> {t.remediation_hint}
                  </div>
                )}
                <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#9ca3af", flexWrap: "wrap" }}>
                  {t.effort_estimate && <span>Effort: {t.effort_estimate}</span>}
                  {t.regulation_ref && <span>Ref: {t.regulation_ref}</span>}
                  {t.created_at && <span>Opened: {t.created_at.slice(0, 10)}</span>}
                </div>

                {noteOpen && (
                  <div style={{ marginTop: 10 }}>
                    <textarea
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="Remediation note (required) — what was done and by whom"
                      rows={2}
                      style={{
                        width: "100%", boxSizing: "border-box", padding: 8,
                        border: "1px solid #d1d5db", borderRadius: 6, fontSize: 13,
                        fontFamily: "inherit",
                      }}
                    />
                    <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                      <button
                        onClick={() => markRemediated(t.id)}
                        disabled={updating}
                        style={{ padding: "6px 14px", background: "#0d9488", color: "#fff", border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer" }}
                      >
                        {updating ? "…" : "Confirm"}
                      </button>
                      <button
                        onClick={() => { setNoteFor(null); setNoteText(""); }}
                        disabled={updating}
                        style={{ padding: "6px 14px", background: "transparent", color: "#6b7280", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 12, cursor: "pointer" }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
              {!noteOpen && (
                <div>
                  <button
                    onClick={() => openNote(t.id)}
                    style={{ padding: "6px 14px", background: "#0d9488", color: "#fff", border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer" }}
                  >
                    Mark Complete
                  </button>
                </div>
              )}
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
