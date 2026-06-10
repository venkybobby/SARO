import React, { useState } from "react";
import { Eye, EyeOff, Shield } from "lucide-react";
import { Button, Input } from "../components/ui/index.jsx";

function parseJwtPayload(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return {};
  }
}

/**
 * Enterprise SSO entry point — collapsed by default. Redirects to the
 * SP-initiated SAML flow at GET /api/v1/sso/login/{tenant_slug} (routers/sso.py).
 */
function SsoEntry() {
  const [open, setOpen] = useState(false);
  const [slug, setSlug] = useState("");

  function handleSso(e) {
    e.preventDefault();
    if (!slug.trim()) return;
    window.location.href = `/api/v1/sso/login/${encodeURIComponent(slug.trim())}`;
  }

  if (!open) {
    return (
      <div style={{ textAlign: "center", marginTop: "var(--space-4)" }}>
        <button
          type="button"
          onClick={() => setOpen(true)}
          style={{
            background: "none", border: "none", cursor: "pointer",
            fontSize: "var(--text-sm)", color: "var(--color-info)", padding: 0,
          }}
        >
          Sign in with SSO
        </button>
      </div>
    );
  }

  return (
    <div style={{ marginTop: "var(--space-4)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Input
          label="Organization ID"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="acme-corp"
          autoComplete="organization"
        />
      </div>
      <Button type="button" variant="secondary" size="lg" onClick={handleSso} style={{ width: "100%", marginTop: "var(--space-2)" }}>
        Continue with SSO
      </Button>
    </div>
  );
}

export default function Login({ onLogin, sessionExpired }) {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [showPw,   setShowPw]   = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [errors,   setErrors]   = useState({});

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setErrors({});
    try {
      const r = await fetch("/api/v1/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        if (Array.isArray(data.detail)) {
          // 422 validation errors carry structured {loc, msg} — map loc to the field
          const fieldErrors = {};
          for (const d of data.detail) {
            const field = d.loc?.[d.loc.length - 1];
            if (field === "email" || field === "password") fieldErrors[field] = d.msg;
            else fieldErrors.form = d.msg || JSON.stringify(d);
          }
          setErrors(fieldErrors);
          return;
        }
        // 401 invalid-credential errors deliberately don't disclose which field is
        // wrong (avoids account enumeration) — surface as a form-level error only.
        throw new Error(data.detail || `Login failed (${r.status})`);
      }
      const { access_token } = await r.json();

      let userProfile = parseJwtPayload(access_token);
      try {
        const meRes = await fetch("/api/v1/auth/me", {
          headers: { Authorization: `Bearer ${access_token}` },
        });
        if (meRes.ok) userProfile = { ...userProfile, ...(await meRes.json()) };
      } catch {
        /* Use JWT payload as fallback */
      }
      onLogin(access_token, userProfile);
    } catch (err) {
      setErrors({ form: err.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--color-bg-base)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "var(--space-6)",
    }}>
      <form
        onSubmit={handleSubmit}
        noValidate
        style={{
          background: "var(--color-bg-surface)",
          border: "1px solid var(--color-border-default)",
          borderRadius: "var(--radius-xl)",
          padding: "var(--space-10) var(--space-8)",
          width: "100%", maxWidth: 400,
          boxShadow: "var(--shadow-lg)",
        }}
      >
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: "var(--space-8)" }}>
          <Shield size={36} color="var(--color-info)" style={{ marginBottom: "var(--space-3)" }} />
          <h1 style={{
            fontSize: "var(--text-xl)", fontWeight: "var(--weight-semibold)",
            color: "var(--color-text-primary)", fontFamily: "var(--font-display)",
            marginBottom: "var(--space-1)",
          }}>
            Sign in to SARO
          </h1>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
            Smart AI Risk Orchestrator
          </p>
        </div>

        {/* Session expired banner */}
        {sessionExpired && (
          <div role="alert" aria-live="assertive" style={{
            background: "var(--color-medium-bg)",
            border: "1px solid var(--color-medium-border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3) var(--space-4)",
            marginBottom: "var(--space-5)",
            fontSize: "var(--text-sm)", color: "var(--color-medium)",
          }}>
            Your session has expired — please sign in again.
          </div>
        )}

        {/* Form-level error */}
        {errors.form && (
          <div role="alert" style={{
            background: "var(--color-critical-bg)",
            border: "1px solid var(--color-critical-border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3) var(--space-4)",
            marginBottom: "var(--space-5)",
            fontSize: "var(--text-sm)", color: "var(--color-critical)",
          }}>
            {errors.form}
          </div>
        )}

        {/* Email */}
        <div style={{ marginBottom: "var(--space-4)" }}>
          <Input
            label="Work email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus={!sessionExpired}
            autoComplete="email"
            placeholder="you@company.com"
            disabled={loading}
            error={errors.email}
          />
        </div>

        {/* Password */}
        <div style={{ marginBottom: "var(--space-6)" }}>
          <div style={{ position: "relative" }}>
            <Input
              label="Password"
              type={showPw ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              disabled={loading}
              error={errors.password}
            />
            <button
              type="button"
              aria-label={showPw ? "Hide password" : "Show password"}
              onClick={() => setShowPw((v) => !v)}
              style={{
                position: "absolute", right: 10,
                top: errors.password ? "calc(50% - 10px)" : "calc(50% + 6px)",
                transform: "translateY(-50%)",
                background: "none", border: "none", cursor: "pointer",
                color: "var(--color-text-muted)", padding: 2,
              }}
            >
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        <Button type="submit" loading={loading} size="lg" style={{ width: "100%" }}>
          Sign in
        </Button>

        <SsoEntry />

        <div style={{ textAlign: "center", marginTop: "var(--space-5)" }}>
          <a href="/demo" style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
            View public demo
          </a>
        </div>
      </form>
    </div>
  );
}
