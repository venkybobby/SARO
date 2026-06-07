/**
 * App shell — client-side routing for the SARO React frontend.
 *
 * Routes:
 *   /              → redirect to /login  (entry point for all users)
 *   /login         → Login page (unauthenticated) OR redirect to /dashboard (authenticated)
 *   /demo          → DemoEntry  (public, auto-fetches read-only demo JWT — accessible directly)
 *   /dashboard     → Dashboard  (authenticated) OR redirect to /login (unauthenticated)
 *   *              → redirect to /login
 */
import React, { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Dashboard  from "./pages/Dashboard";
import DemoEntry  from "./pages/DemoEntry";
import Login      from "./pages/Login";

export default function App() {
  const [authToken,  setAuthToken]  = useState(null);
  const [tenantId,   setTenantId]   = useState(null);

  function handleLogin(token, tid) {
    setAuthToken(token);
    setTenantId(tid);
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/demo" element={<DemoEntry />} />
        <Route
          path="/login"
          element={
            authToken
              ? <Navigate to="/dashboard" replace />
              : <Login onLogin={handleLogin} />
          }
        />
        <Route
          path="/dashboard"
          element={
            authToken
              ? <Dashboard token={authToken} tenantId={tenantId} />
              : <Navigate to="/login" replace />
          }
        />
        {/* Default: login is the entry point. /demo remains publicly accessible via direct URL. */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
