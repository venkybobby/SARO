import React, { useState } from "react";
import {
  Building2, Users, Plug, Bell, Shield, AlertTriangle,
  Check, X,
} from "lucide-react";
import { Button, ConfirmDialog, PageHeader } from "../components/ui/index.jsx";

const SETTING_GROUPS = [
  { id: "general",        label: "General",              icon: Building2 },
  { id: "users",          label: "Users & Permissions",  icon: Users },
  { id: "integrations",   label: "Integrations",         icon: Plug },
  { id: "notifications",  label: "Notifications",        icon: Bell },
  { id: "framework",      label: "Risk Framework",       icon: Shield },
  { id: "danger",         label: "Danger Zone",          icon: AlertTriangle },
];

const PERMISSIONS = [
  { key: "view_risks",    label: "View risks",           desc: "Read access to the risk register" },
  { key: "create_risks",  label: "Create risks",         desc: "Add new risks to the register" },
  { key: "edit_risks",    label: "Edit risks",           desc: "Modify existing risk records" },
  { key: "delete_risks",  label: "Delete risks",         desc: "Remove risks from the register" },
  { key: "view_insights", label: "View AI insights",     desc: "Access SARO-generated recommendations" },
  { key: "manage_users",  label: "Manage users",         desc: "Invite and remove team members" },
  { key: "view_reports",  label: "View reports",         desc: "Access analytics and audit exports" },
  { key: "admin_settings",label: "Admin settings",       desc: "Change organization-wide settings" },
];

const ROLES = ["Admin", "Risk Manager", "Viewer", "Auditor"];

const ROLE_PERMS = {
  Admin:        ["view_risks","create_risks","edit_risks","delete_risks","view_insights","manage_users","view_reports","admin_settings"],
  "Risk Manager": ["view_risks","create_risks","edit_risks","view_insights","view_reports"],
  Viewer:       ["view_risks","view_reports"],
  Auditor:      ["view_risks","view_insights","view_reports"],
};

function GeneralSettings({ onSave }) {
  const [orgName, setOrgName] = useState("Acme Corp");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <section>
        <h2 style={{ fontSize: "var(--text-md)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)", fontFamily: "var(--font-display)", marginBottom: "var(--space-4)" }}>Organization</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", maxWidth: 480 }}>
          <div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--weight-medium)", color: "var(--color-text-secondary)", marginBottom: "var(--space-1)" }}>
              Organization name
            </label>
            <input
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              style={{
                width: "100%", padding: "8px 12px",
                background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
                borderRadius: "var(--radius-md)", color: "var(--color-text-primary)",
                fontSize: "var(--text-base)", fontFamily: "var(--font-body)", outline: "none",
              }}
              onFocus={(e) => { e.target.style.borderColor = "var(--color-info)"; e.target.style.boxShadow = "var(--focus-ring)"; }}
              onBlur={(e) => { e.target.style.borderColor = "var(--color-border-default)"; e.target.style.boxShadow = "none"; }}
            />
          </div>
          <Button variant="primary" size="sm" onClick={onSave}>Save changes</Button>
        </div>
      </section>
    </div>
  );
}

function UsersSettings() {
  return (
    <div>
      <h2 style={{ fontSize: "var(--text-md)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)", fontFamily: "var(--font-display)", marginBottom: "var(--space-6)" }}>
        Permissions Matrix
      </h2>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 600 }}>
          <thead>
            <tr>
              <th style={{ padding: "var(--space-2) var(--space-3)", textAlign: "left", fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid var(--color-border-subtle)" }}>
                Permission
              </th>
              {ROLES.map((role) => (
                <th key={role} style={{ padding: "var(--space-2) var(--space-3)", textAlign: "center", fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", borderBottom: "1px solid var(--color-border-subtle)" }}>
                  {role}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERMISSIONS.map((perm, idx) => (
              <tr key={perm.key} style={{ background: idx % 2 === 0 ? "transparent" : "var(--color-bg-elevated)" }}>
                <td style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--color-border-subtle)" }}>
                  <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-primary)", fontWeight: "var(--weight-medium)" }}>{perm.label}</div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>{perm.desc}</div>
                </td>
                {ROLES.map((role) => (
                  <td key={role} style={{ padding: "var(--space-3)", textAlign: "center", borderBottom: "1px solid var(--color-border-subtle)" }}>
                    {ROLE_PERMS[role]?.includes(perm.key) ? (
                      <Check size={14} color="var(--color-low)" />
                    ) : (
                      <X size={14} color="var(--color-text-muted)" style={{ opacity: 0.3 }} />
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DangerZone() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  return (
    <div>
      <h2 style={{ fontSize: "var(--text-md)", fontWeight: "var(--weight-semibold)", color: "var(--color-critical)", fontFamily: "var(--font-display)", marginBottom: "var(--space-4)" }}>
        Danger Zone
      </h2>
      <div style={{
        border: "1px solid var(--color-critical-border)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
      }}>
        <div style={{
          padding: "var(--space-5)",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-4)",
          flexWrap: "wrap",
        }}>
          <div>
            <div style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)" }}>Delete organization</div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: 2 }}>
              Permanently delete all risks, controls, and user data. Cannot be undone.
            </div>
          </div>
          <Button variant="danger" size="sm" onClick={() => setConfirmOpen(true)}>
            <AlertTriangle size={13} /> Delete organization
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete organization"
        description="This will permanently delete all risks, controls, and user data. This cannot be undone."
        confirmLabel="Yes, delete permanently"
        onConfirm={() => setConfirmOpen(false)}
        onCancel={() => setConfirmOpen(false)}
        requireTyping="delete"
      />
    </div>
  );
}

const GROUP_COMPONENTS = {
  general:       GeneralSettings,
  users:         UsersSettings,
  integrations:  () => <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Integration configuration coming soon.</div>,
  notifications: () => <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Notification preferences coming soon.</div>,
  framework:     () => <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>Risk framework configuration coming soon.</div>,
  danger:        DangerZone,
};

export default function Settings({ token, onSave }) {
  const [activeGroup, setActiveGroup] = useState("general");

  const ActiveComponent = GROUP_COMPONENTS[activeGroup] || (() => null);

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Settings"
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>Settings</span></>}
      />

      <div style={{ display: "flex", minHeight: "calc(100vh - 73px)" }}>
        {/* Left nav */}
        <aside style={{
          width: 220, flexShrink: 0,
          background: "var(--color-bg-surface)",
          borderRight: "1px solid var(--color-border-subtle)",
          padding: "var(--space-4) 0",
        }}>
          {SETTING_GROUPS.map(({ id, label, icon: Icon }) => {
            const isActive = activeGroup === id;
            const isDanger = id === "danger";
            return (
              <button
                key={id}
                onClick={() => setActiveGroup(id)}
                style={{
                  display: "flex", alignItems: "center", gap: "var(--space-3)",
                  width: "100%", padding: "var(--space-3) var(--space-4)",
                  background: isActive ? "var(--color-bg-overlay)" : "transparent",
                  borderLeft: `3px solid ${isActive ? (isDanger ? "var(--color-critical)" : "var(--color-info)") : "transparent"}`,
                  border: "none",
                  color: isDanger ? "var(--color-critical)" : isActive ? "var(--color-text-primary)" : "var(--color-text-muted)",
                  fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
                  cursor: "pointer", textAlign: "left",
                  transition: "background var(--transition-fast)",
                  outline: "none",
                  marginTop: isDanger ? "var(--space-4)" : 0,
                  borderTop: isDanger ? "1px solid var(--color-border-subtle)" : "none",
                  paddingTop: isDanger ? "var(--space-4)" : "var(--space-3)",
                }}
                onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "var(--color-bg-elevated)"; }}
                onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
              >
                <Icon size={15} />
                {label}
              </button>
            );
          })}
        </aside>

        {/* Content */}
        <main style={{ flex: 1, padding: "var(--space-8)", overflowY: "auto", maxWidth: 800 }}>
          <ActiveComponent onSave={onSave} token={token} />
        </main>
      </div>
    </div>
  );
}
