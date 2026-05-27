/**
 * S-205B: Demo entry point — auto-fetches the public demo JWT and renders Dashboard.
 * Token is held in React state only (not localStorage); sessionStorage only for tenantId.
 * CRITICAL: Never store the demo JWT in localStorage.
 */
import React, { useEffect, useState } from "react";
import Dashboard from "./Dashboard";

const SARO_API_URL = process.env.REACT_APP_SARO_API_URL || "";

function parseJwtPayload(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch {
    return {};
  }
}

async function fetchDemoToken() {
  const r = await fetch(`${SARO_API_URL}/api/v1/demo/token`);
  if (!r.ok) throw new Error(`Demo token API ${r.status}`);
  return r.json();
}

export default function DemoEntry() {
  const [token,    setToken]    = useState(null);
  const [tenantId, setTenantId] = useState(null);
  const [error,    setError]    = useState(null);
  const [attempt,  setAttempt]  = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchDemoToken()
      .then((data) => {
        if (cancelled) return;
        const jwt = data.access_token;
        const payload = parseJwtPayload(jwt);
        const tid = payload.tenant_id || payload.sub;
        setToken(jwt);
        setTenantId(tid);
        if (tid) sessionStorage.setItem("saro_demo_tenant_id", tid);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Failed to load demo session.");
      });
    return () => { cancelled = true; };
  }, [attempt]);

  if (token && tenantId) {
    return <Dashboard token={token} tenantId={tenantId} isDemo />;
  }

  return (
    <div style={{
      minHeight: "100vh", background: "#0f1117", color: "#e2e8f0",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{
        background: "#13192b", border: "1px solid #1e293b", borderRadius: 16,
        padding: "48px 56px", maxWidth: 440, width: "100%", textAlign: "center",
      }}>
        <div style={{ fontSize: 28, fontWeight: 800, color: "#14b8a6", marginBottom: 8 }}>
          SARO
        </div>
        <div style={{ fontSize: 14, color: "#475569", marginBottom: 36 }}>
          Smart AI Risk Orchestrator — Demo
        </div>

        {!error ? (
          <>
            <div style={{
              width: 40, height: 40, border: "3px solid #1e293b",
              borderTop: "3px solid #14b8a6", borderRadius: "50%",
              animation: "spin 0.8s linear infinite", margin: "0 auto 20px",
            }} />
            <div style={{ fontSize: 13, color: "#64748b" }}>Loading demo session…</div>
          </>
        ) : (
          <div style={{
            background: "#1c0a0a", border: "1px solid #7f1d1d", borderRadius: 8, padding: "16px 20px",
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#f87171", marginBottom: 6 }}>
              Demo unavailable
            </div>
            <div style={{ fontSize: 12, color: "#fca5a5", lineHeight: 1.6 }}>{error}</div>
            <button
              style={{
                marginTop: 20, padding: "8px 24px", borderRadius: 8, border: "none",
                cursor: "pointer", background: "#0d9488", color: "#fff", fontSize: 13, fontWeight: 600,
              }}
              onClick={() => setAttempt((n) => n + 1)}
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
