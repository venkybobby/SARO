/**
 * SARO API client — centralised endpoint calls for the framework dashboard.
 * All functions read SARO_API_URL from the environment (set at build time).
 */
const SARO_API_URL = process.env.REACT_APP_SARO_API_URL || "";

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchDashboardMetrics(token) {
  const r = await fetch(`${SARO_API_URL}/api/v1/dashboard`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`Dashboard API ${r.status}`);
  return r.json();
}

export async function fetchRecentAudits(token, tenantId, limit = 20) {
  const url = `${SARO_API_URL}/api/v1/audits?tenant_id=${tenantId}&limit=${limit}&sort=desc`;
  const r = await fetch(url, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`Audits API ${r.status}`);
  return r.json();
}

// GAP-009: vertical param wires the dashboard vertical switcher to backend filter
export async function fetchComplianceCoverage(token, tenantId, window = "7d", vertical = null) {
  let url = `${SARO_API_URL}/api/v1/compliance-matrix/coverage?tenant_id=${tenantId}&window=${window}`;
  if (vertical) url += `&vertical=${encodeURIComponent(vertical)}`;
  const r = await fetch(url, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`Coverage API ${r.status}`);
  return r.json();
}

// GAP-009: vertical param wires the dashboard vertical switcher to backend filter
export async function fetchRiskDashboard(token, tenantId, vertical = null) {
  let url = `${SARO_API_URL}/api/v1/risk_dashboard?tenant_id=${tenantId}`;
  if (vertical) url += `&vertical=${encodeURIComponent(vertical)}`;
  const r = await fetch(url, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`Risk dashboard API ${r.status}`);
  return r.json();
}

export async function fetchQueueStatus(token, tenantId) {
  const url = `${SARO_API_URL}/api/v1/hf/queue/status?tenant_id=${tenantId}`;
  const r = await fetch(url, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`Queue status API ${r.status}`);
  return r.json();
}

export async function fetchLatestAudit(token) {
  const r = await fetch(
    `${SARO_API_URL}/api/v1/audits?limit=1&sort=desc`,
    { headers: authHeaders(token) }
  );
  if (!r.ok) throw new Error(`Audits API ${r.status}`);
  return r.json();
}
