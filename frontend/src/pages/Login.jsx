/**
 * Login — JWT login. After token, fetches /api/v1/auth/me for full user profile (persona, role).
 * Accepts sessionExpired prop to show expiry warning.
 */
import React, { useState } from "react";

function parseJwtPayload(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return {};
  }
}

export default function Login({ onLogin, sessionExpired }) {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // 1. Get token
      const r = await fetch("/api/v1/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        const detail = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
          : data.detail;
        throw new Error(detail || `Login failed (${r.status})`);
      }
      const { access_token } = await r.json();

      // 2. Fetch full user profile (includes persona_role, role, tenant_id)
      let userProfile = parseJwtPayload(access_token);
      try {
        const meRes = await fetch("/api/v1/auth/me", {
          headers: { Authorization: `Bearer ${access_token}` },
        });
        if (meRes.ok) {
          userProfile = { ...userProfile, ...(await meRes.json()) };
        }
      } catch {
        // Use JWT payload as fallback
      }

      onLogin(access_token, userProfile);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    width: "100%", padding: "10px 12px", borderRadius: 8,
    border: "1px solid #d1d5db", fontSize: 14, outline: "none",
    boxSizing: "border-box",
  };

  return (
    <div style={{
      minHeight: "100vh", background: "#f9fafb",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <form
        onSubmit={handleSubmit}
        style={{
          background: "#fff", borderRadius: 16, padding: "40px 48px",
          boxShadow: "0 4px 24px rgba(0,0,0,0.08)", width: 380,
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 36, marginBottom: 6 }}>🛡️</div>
          <div style={{ fontSize: 28, fontWeight: 800, color: "#0d9488" }}>SARO</div>
          <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
            Smart AI Risk Orchestrator — Enterprise Governance Platform
          </div>
        </div>

        {sessionExpired && (
          <div style={{
            background: "#fffbeb", border: "1px solid #fde68a",
            borderRadius: 8, padding: "10px 14px", marginBottom: 16,
            fontSize: 13, color: "#92400e",
          }}>
            ⏱ Your session has expired — please sign in again.
          </div>
        )}

        {error && (
          <div style={{
            background: "#fef2f2", border: "1px solid #fca5a5",
            borderRadius: 8, padding: "10px 14px", marginBottom: 20,
            fontSize: 13, color: "#b91c1c",
          }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Work Email</label>
          <input
            type="email" value={email}
            onChange={(e) => setEmail(e.target.value)}
            required placeholder="operator@acme.com" style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Password</label>
          <input
            type="password" value={password}
            onChange={(e) => setPassword(e.target.value)}
            required placeholder="••••••••" style={inputStyle}
          />
        </div>

        <button
          type="submit" disabled={loading}
          style={{
            width: "100%", padding: "11px 0", borderRadius: 8, border: "none",
            background: loading ? "#99f6e4" : "#0d9488", color: "#fff",
            fontSize: 15, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Signing in…" : "Sign in →"}
        </button>

        <div style={{ textAlign: "center", marginTop: 20 }}>
          <a href="/demo" style={{ fontSize: 13, color: "#0d9488", textDecoration: "none" }}>
            View public demo instead →
          </a>
        </div>
      </form>
    </div>
  );
}
