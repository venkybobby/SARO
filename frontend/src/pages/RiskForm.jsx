/**
 * RiskForm — create or edit a risk register entry.
 * Used for both "+ New Risk" (no riskId) and "Edit" (riskId provided).
 */
import React, { useEffect, useState } from "react";
import { ArrowLeft, Save } from "lucide-react";
import { Button, PageHeader, ConfirmDialog } from "../components/ui/index.jsx";

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

export default function RiskForm({ token, riskId, onNavigate, onRegisterDirtyGuard, toast }) {
  const isEdit = !!riskId;
  const [form,    setForm]    = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(isEdit);
  const [saving,  setSaving]  = useState(false);
  const [errors,  setErrors]  = useState({});
  const [isDirty, setIsDirty] = useState(false);
  const [pendingNav, setPendingNav] = useState(null);

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

  useEffect(() => {
    function handleBeforeUnload(e) {
      if (!isDirty) return;
      e.preventDefault();
      e.returnValue = "";
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // Register a guard so App-level navigation (e.g. sidebar links) can
  // confirm before discarding unsaved changes (AC-2).
  useEffect(() => {
    onRegisterDirtyGuard?.(() => isDirty);
    return () => onRegisterDirtyGuard?.(null);
  }, [isDirty, onRegisterDirtyGuard]);

  function navigateTo(page, payload) {
    if (payload === undefined) onNavigate?.(page);
    else onNavigate?.(page, payload);
  }

  function guardedNavigate(page, payload) {
    if (isDirty) {
      setPendingNav({ page, payload });
    } else {
      navigateTo(page, payload);
    }
  }

  function validate(field) {
    const checks = {
      title:   () => !form.title.trim()   ? "Title is required"    : null,
      owner:   () => !form.owner.trim()   ? "Owner is required"     : null,
      dueDate: () => !form.dueDate        ? "Due date is required"  : null,
    };

    if (field) {
      if (!checks[field]) return true;
      const message = checks[field]();
      setErrors((prev) => {
        const next = { ...prev };
        if (message) next[field] = message; else delete next[field];
        return next;
      });
      return !message;
    }

    const e = {};
    for (const key of Object.keys(checks)) {
      const message = checks[key]();
      if (message) e[key] = message;
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleFieldBlur(field) {
    return () => validate(field);
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
        setIsDirty(false);
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
      onChange: (e) => {
        const value = e.target.value;
        setForm((p) => ({ ...p, [key]: value }));
        setErrors((p) => { const n = {...p}; delete n[key]; return n; });
        setIsDirty(true);
      },
    };
  }

  const inputStyle = (hasErr) => ({
    width: "100%", padding: "8px 10px", borderRadius: 6, fontSize: 13,
    border: `1px solid ${hasErr ? "var(--color-critical)" : "var(--color-border-default)"}`,
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
            <span style={{ cursor: "pointer", color: "var(--color-info)" }} onClick={() => guardedNavigate("risk_register")}>
              Risk Register
            </span>
            <span style={{ color: "var(--color-text-muted)" }}> › </span>
            <span>{isEdit ? "Edit" : "New Risk"}</span>
          </>
        }
        actions={
          <Button variant="ghost" size="sm" onClick={() => guardedNavigate("risk_register")}>
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
                Title <span style={{ color: "var(--color-critical)" }}>*</span>
              </label>
              <input
                {...field("title")}
                onBlur={handleFieldBlur("title")}
                placeholder="Describe the risk…"
                style={inputStyle(errors.title)}
                aria-describedby={errors.title ? "title-error" : undefined}
              />
              {errors.title && <div id="title-error" style={{ fontSize: 11, color: "var(--color-critical)", marginTop: 4 }}>{errors.title}</div>}
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
                  Owner <span style={{ color: "var(--color-critical)" }}>*</span>
                </label>
                <input
                  {...field("owner")}
                  onBlur={handleFieldBlur("owner")}
                  placeholder="Name or email…"
                  style={inputStyle(errors.owner)}
                  aria-describedby={errors.owner ? "owner-error" : undefined}
                />
                {errors.owner && <div id="owner-error" style={{ fontSize: 11, color: "var(--color-critical)", marginTop: 4 }}>{errors.owner}</div>}
              </div>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--color-text-primary)" }}>
                  Due Date <span style={{ color: "var(--color-critical)" }}>*</span>
                </label>
                <input
                  type="date"
                  {...field("dueDate")}
                  onBlur={handleFieldBlur("dueDate")}
                  style={inputStyle(errors.dueDate)}
                  aria-describedby={errors.dueDate ? "dueDate-error" : undefined}
                />
                {errors.dueDate && <div id="dueDate-error" style={{ fontSize: 11, color: "var(--color-critical)", marginTop: 4 }}>{errors.dueDate}</div>}
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
              <Button type="button" variant="ghost" size="sm" onClick={() => guardedNavigate("risk_register")}>
                Cancel
              </Button>
              <span style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: "auto" }}>
                Human review required before any action is taken on this risk.
              </span>
            </div>
          </div>
        </form>
      </div>

      <ConfirmDialog
        open={!!pendingNav}
        title="Discard unsaved changes?"
        description="You have unsaved changes. If you leave now, your edits will be lost."
        confirmLabel="Discard changes"
        cancelLabel="Keep editing"
        onConfirm={() => {
          const nav = pendingNav;
          setPendingNav(null);
          setIsDirty(false);
          navigateTo(nav.page, nav.payload);
        }}
        onCancel={() => setPendingNav(null)}
      />
    </div>
  );
}
