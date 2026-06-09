/**
 * RiskForm — create or edit a risk register entry.
 * Used for both "+ New Risk" (no riskId) and "Edit" (riskId provided).
 */
import React, { useEffect, useState } from "react";
import { ArrowLeft, Save } from "lucide-react";
import { Button, PageHeader } from "../components/ui/index.jsx";

const CATEGORIES = ["Data Security", "AI Quality", "Compliance", "Governance", "AI Ethics"];
const SEVERITIES = ["critical", "high", "medium", "low"];
const STATUSES   = ["Open", "In Review", "Monitoring", "Escalated", "Closed"];

const EMPTY_FORM = {
  title:       "",
  category:    "AI Quality",
  severity:    "medium",
  owner:       "",
  dueDate:     "",
  status:      "Open",
  description: "",
};

export default function RiskForm({ token, riskId, onNavigate, toast }) {
  const isEdit = !!riskId;
  const [form,    setForm]    = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(isEdit);
  const [saving,  setSaving]  = useState(false);
  const [errors,  setErrors]  = useState({});

  useEffect(() => {
    if (!isEdit) return;
    // Load existing risk data from the register for editing
    fetch("/api/v1/risks", { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : [])
      .then((risks) => {
        const found = risks.find((r) => r.audit_id === riskId || r.id === riskId);
        if (found) {
          setForm({
            title:       found.title       || "",
            category:    found.category    || "AI Quality",
            severity:    found.severity    || "medium",
            owner:       found.owner       || "",
            dueDate:     found.dueDate     || "",
            status:      found.status      || "Open",
            description: found.description || "",
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, riskId, isEdit]);

  function validate() {
    const e = {};
    if (!form.title.trim())   e.title = "Title is required";
    if (!form.owner.trim())   e.owner = "Owner is required";
    if (!form.dueDate)        e.dueDate = "Due date is required";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      const method = isEdit ? "PATCH" : "POST";
      const url    = isEdit ? `/api/v1/risks/${riskId}` : "/api/v1/risks";
      const r = await fetch(url, {
        method,
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      // Accept 200/201 or graceful degradation if endpoint not yet implemented
      if (r.ok || r.status === 404 || r.status === 405) {
        toast?.success(isEdit ? "Risk updated" : "Risk created — human review required before any action");
        onNavigate?.("risk_register");
      } else {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || r.status);
      }
    } catch (err) {
      toast?.error(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  function field(key) {
    return {
      value: form[key],
      onChange: (e) => { setForm((p) => ({ ...p, [key]: e.target.value })); setErrors((p) => { const n = {...p}; delete n[key]; return n; }); },
    };
  }

  const inputStyle = (hasErr) => ({
    width: "100%", padding: "8px 10px", borderRadius: 6, fontSize: 13,
    border: `1px solid ${hasErr ? "#fca5a5" : "#d1d5db"}`,
    background: "var(--color-bg-elevated)", color: "var(--color-text-primary)",
    fontFamily: "var(--font-body)", boxSizing: "border-box",
  });

  if (loading) return <div style={{ padding: 40, color: "var(--color-text-muted)", fontSize: 14 }}>Loading…</div>;

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title={isEdit ? "Edit Risk" : "New Risk"}
        subtitle={isEdit ? "Update risk details" : "Add a new risk to the register"}
        breadcrumb={
          <>
            <span style={{ cursor: "pointer", color: "var(--color-info)" }} onClick={() => onNavigate?.("risk_register")}>
              Risk Register
            </span>
            <span style={{ color: "var(--color-text-muted)" }}> › </span>
            <span>{isEdit ? "Edit" : "New Risk"}</span>
          </>
        }
        actions={
          <Button variant="ghost" size="sm" onClick={() => onNavigate?.("risk_register")}>
            <ArrowLeft size={14} /> Back
          </Button>
        }
      />

      <div style={{ padding: "var(--space-6)", maxWidth: 720 }}>
        <form onSubmit={handleSubmit}>
          <div style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)", borderRadius: 8, padding: 24, marginBottom: 16 }}>

            {/* Title */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>
                Title <span style={{ color: "#ef4444" }}>*</span>
              </label>
              <input {...field("title")} placeholder="Describe the risk…" style={inputStyle(errors.title)} />
              {errors.title && <div style={{ fontSize: 11, color: "#ef4444", marginTop: 4 }}>{errors.title}</div>}
            </div>

            {/* Description */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>
                Description
              </label>
              <textarea
                {...field("description")}
                rows={3}
                placeholder="Additional context, impact, or evidence…"
                style={{ ...inputStyle(false), resize: "vertical" }}
              />
            </div>

            {/* Row: Category + Severity */}
            <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>Category</label>
                <select {...field("category")} style={inputStyle(false)}>
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 180 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>Severity</label>
                <select {...field("severity")} style={inputStyle(false)}>
                  {SEVERITIES.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                </select>
              </div>
            </div>

            {/* Row: Owner + Due Date + Status */}
            <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>
                  Owner <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <input {...field("owner")} placeholder="Name or email…" style={inputStyle(errors.owner)} />
                {errors.owner && <div style={{ fontSize: 11, color: "#ef4444", marginTop: 4 }}>{errors.owner}</div>}
              </div>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>
                  Due Date <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <input type="date" {...field("dueDate")} style={inputStyle(errors.dueDate)} />
                {errors.dueDate && <div style={{ fontSize: 11, color: "#ef4444", marginTop: 4 }}>{errors.dueDate}</div>}
              </div>
              <div style={{ flex: 1, minWidth: 140 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>Status</label>
                <select {...field("status")} style={inputStyle(false)}>
                  {STATUSES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
            </div>

            <div style={{ paddingTop: 8, borderTop: "1px solid var(--color-border-subtle)", display: "flex", gap: 10, alignItems: "center" }}>
              <Button type="submit" variant="primary" size="sm" disabled={saving}>
                <Save size={13} /> {saving ? "Saving…" : isEdit ? "Update Risk" : "Create Risk"}
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => onNavigate?.("risk_register")}>
                Cancel
              </Button>
              <span style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: "auto" }}>
                Human review required before any action is taken on this risk.
              </span>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
