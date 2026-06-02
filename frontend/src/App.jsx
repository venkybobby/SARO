/**
 * App shell — client-side routing for the SARO React frontend.
 *
 * Routes:
 *   /demo          → DemoEntry  (public, auto-fetches read-only demo JWT)
 *   /dashboard     → Dashboard  (authenticated)
 *   /              → redirect to /demo
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
        <Route path="/" element={<Navigate to="/demo" replace />} />
        <Route path="*" element={<Navigate to="/demo" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
