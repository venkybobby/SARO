/**
 * Login — standard JWT login for non-demo users.
 * Posts to POST /api/v1/auth/token with JSON body { email, password }.
 */
import React, { useState } from "react";

const SARO_API_URL = process.env.REACT_APP_SARO_API_URL || "";

function parseJwtPayload(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return {};
  }
}

export default function Login({ onLogin }) {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${SARO_API_URL}/api/v1/auth/token`, {
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
      const payload = parseJwtPayload(access_token);
      onLogin(access_token, payload.tenant_id || payload.sub);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    width: "100%", padding: "10px 12px", borderRadius: 8,
    border: "1px solid #d1d5db", fontSize: 14, outline: "none",
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
          boxShadow: "0 4px 24px rgba(0,0,0,0.08)", width: 360,
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 28, fontWeight: 800, color: "#0d9488" }}>SARO</div>
          <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
            Smart AI Risk Orchestrator
          </div>
        </div>

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
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="you@example.com"
            style={inputStyle}
          />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="••••••••"
            style={inputStyle}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%", padding: "11px 0", borderRadius: 8, border: "none",
            background: loading ? "#99f6e4" : "#0d9488", color: "#fff",
            fontSize: 15, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Signing in…" : "Sign in"}
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
