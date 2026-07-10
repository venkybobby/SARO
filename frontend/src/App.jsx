/**
 * App shell — full SARO React frontend with sidebar navigation.
 *
 * Auth token is persisted in localStorage so page refresh doesn't log out.
 * Sidebar navigation matches the Streamlit persona-based tab list exactly.
 */
import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login    from "./pages/Login";
import DemoEntry from "./pages/DemoEntry";
import AppShell from "./components/AppShell.jsx";
import { ToastContainer } from "./components/ui/index.jsx";
import { useToast } from "./hooks/useToast.js";
import { parseJwt } from "./utils/jwt.js";

function isTokenValid(token) {
  if (!token) return false;
  try {
    const payload = parseJwt(token);
    return Date.now() / 1000 < (payload.exp || 0) - 60;
  } catch {
    return false;
  }
}

const LS_TOKEN = "saro_token";
const LS_USER  = "saro_user";

export default function App() {
  const { toasts, dismiss, toast } = useToast();

  const [token, setToken] = useState(() => {
    const stored = localStorage.getItem(LS_TOKEN);
    return isTokenValid(stored) ? stored : null;
  });
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem(LS_USER) || "null"); } catch { return null; }
  });
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    const check = () => {
      if (token && !isTokenValid(token)) {
        setExpired(true);
        setToken(null);
        setUser(null);
        localStorage.removeItem(LS_TOKEN);
        localStorage.removeItem(LS_USER);
      }
    };
    check();
    const t = setInterval(check, 60000);
    return () => clearInterval(t);
  }, [token]);

  function handleLogin(newToken, userPayload) {
    setToken(newToken);
    setUser(userPayload);
    setExpired(false);
    localStorage.setItem(LS_TOKEN, newToken);
    localStorage.setItem(LS_USER, JSON.stringify(userPayload));
    toast.success("Signed in successfully");
  }

  function handleSignOut() {
    setToken(null);
    setUser(null);
    localStorage.removeItem(LS_TOKEN);
    localStorage.removeItem(LS_USER);
  }

  function handleUserUpdate(updatedUser) {
    setUser(updatedUser);
    localStorage.setItem(LS_USER, JSON.stringify(updatedUser));
  }

  const isAuth = token && isTokenValid(token);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/demo" element={<DemoEntry />} />
        <Route
          path="/login"
          element={
            isAuth
              ? <Navigate to="/app" replace />
              : <Login onLogin={handleLogin} sessionExpired={expired} />
          }
        />
        <Route
          path="/app"
          element={
            isAuth
              ? <AppShell token={token} user={user} onSignOut={handleSignOut} onUserUpdate={handleUserUpdate} toast={toast} />
              : <Navigate to="/login" replace />
          }
        />
        <Route path="/dashboard" element={<Navigate to="/app" replace />} />
        <Route path="/" element={<Navigate to={isAuth ? "/app" : "/login"} replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>

      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </BrowserRouter>
  );
}
