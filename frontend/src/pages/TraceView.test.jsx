import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import TraceView, { normalizeTrace } from "./TraceView";

// STORY-TRACE-001: the timeline endpoint returns `steps` as an ARRAY with real
// per-gate status. A failing audit must never render as fully passed.
const TIMELINE = {
  steps: [
    { key: "ingest", step: "Ingest", status: "pass", detail: "Data ingested cleanly.", rules_fired: ["1", "data_quality"], confidence: 0.9 },
    { key: "classify", step: "Classify", status: "warn", detail: "Fairness gap flagged.", rules_fired: ["2"], confidence: 0.7 },
    { key: "match", step: "Match", status: "fail", detail: "MIT risk matched.", rules_fired: ["3"], confidence: 0.8 },
    { key: "score", step: "Score", status: "pass", detail: "Scored.", rules_fired: ["4"], confidence: 0.85 },
    { key: "explain", step: "Explain", status: "pending", detail: "", rules_fired: [], confidence: null },
    { key: "remediate", step: "Remediate", status: "pending", detail: "", rules_fired: [], confidence: null },
  ],
  step_count: 6,
  executive_mode: false,
  model_version: "saro-engine-1.0",
  audit_status: "failed",
  risk_score: 0.74,
  rule_pack_hash: "abcdef0123456789aaaa",
  scanned_at: "2026-01-01T00:00:00Z",
};
const AUDIT = { audit_id: "audit-123456789", rule_pack_hash: "abc123def456", created_at: "2026-01-01T00:00:00Z" };

function stubFetch(timeline = TIMELINE, audit = AUDIT, traceOk = true, recent = { ok: true, items: [] }) {
  vi.stubGlobal("fetch", vi.fn((url) => {
    if (url === "/api/v1/audit/audit-123456789/trace") {
      return Promise.resolve({ ok: traceOk, status: traceOk ? 200 : 404, json: () => Promise.resolve(timeline) });
    }
    if (url === "/api/v1/audits/audit-123456789") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(audit) });
    }
    // recent list: /api/v1/audits?limit=10&sort=desc
    return Promise.resolve({ ok: recent.ok, status: recent.ok ? 200 : 403, json: () => Promise.resolve(recent.items || []) });
  }));
}

beforeEach(() => stubFetch());

describe("normalizeTrace (render-contract helper)", () => {
  it("keys the steps array by step key and detects real results", () => {
    const m = normalizeTrace(TIMELINE);
    expect(Object.keys(m.byKey)).toHaveLength(6);
    expect(m.byKey.match.status).toBe("fail");
    expect(m.hasResults).toBe(true);
    expect(m.auditStatus).toBe("failed");
    expect(m.riskScore).toBe(0.74);
  });

  it("treats an empty/absent steps array as all-pending with no results", () => {
    expect(normalizeTrace({ steps: [], audit_status: "completed" }).hasResults).toBe(false);
    expect(normalizeTrace({}).stepCount).toBe(0);
    expect(normalizeTrace(undefined).byKey).toEqual({});
  });
});

describe("TraceView TRACE-001 render contract", () => {
  it("fetches the timeline endpoint (not /traces/{id})", async () => {
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    const urls = fetch.mock.calls.map((c) => c[0]);
    expect(urls).toContain("/api/v1/audit/audit-123456789/trace");
    expect(urls).not.toContain("/api/v1/traces/audit-123456789");
  });

  it("binds the real audit status and risk score in the header", async () => {
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    expect(screen.getByText(/FAILED/)).toBeInTheDocument();
  });

  it("never shows a failing audit as fully passed (no all-green fallback)", async () => {
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    // No step is rendered as "done" (statuses are pass/warn/fail/pending only).
    expect(screen.queryAllByText(/\bdone\b/i)).toHaveLength(0);
    // The failing Match step surfaces a fail status (\bfail\b excludes "FAILED").
    expect(screen.getAllByText(/\bfail\b/i).length).toBeGreaterThanOrEqual(1);
    // Explain + Remediate stay pending (not "done").
    expect(screen.getAllByText(/\bpending\b/i).length).toBeGreaterThanOrEqual(2);
  });

  it("shows an explicit no-records note (not all-green) for a trace with no steps", async () => {
    stubFetch({ steps: [], step_count: 0, audit_status: "completed", risk_score: null });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText(/No trace records/i)).toBeInTheDocument());
    expect(screen.queryAllByText("done")).toHaveLength(0);
  });

  it("renders the audit-meta fetch path without throwing a ReferenceError (FND-004 regression)", async () => {
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText(/rule pack/i)).toBeInTheDocument());
  });
});

describe("TraceView TRACE-008 provenance triple", () => {
  it("renders rule-pack (truncated, full in title), model version and scan time", async () => {
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    expect(screen.getByText(/^Provenance$/i)).toBeInTheDocument();
    // model version from the TIMELINE (not the audit-report fetch)
    expect(screen.getByText("saro-engine-1.0")).toBeInTheDocument();
    // rule-pack hash truncated, full value in title
    const rp = screen.getByText(/abcdef012345…/);
    expect(rp).toBeInTheDocument();
    expect(rp.getAttribute("title")).toBe("abcdef0123456789aaaa");
    // scan time rendered unambiguously (UTC)
    expect(screen.getByText(/2026-01-01 00:00:00 UTC/)).toBeInTheDocument();
  });

  it("shows an explicit 'unavailable' for each missing provenance field (never blank)", async () => {
    // empty audit-report fallback too, so all three fields are genuinely absent
    stubFetch({ ...TIMELINE, rule_pack_hash: null, model_version: null, scanned_at: null }, {});
    render(<TraceView token="t" initialAuditId="audit-123456789" user={{ role: "operator" }} />);
    await waitFor(() => expect(screen.getByText(/^Provenance$/i)).toBeInTheDocument());
    // all three fields fall back to the explicit placeholder
    expect(screen.getAllByText("unavailable").length).toBeGreaterThanOrEqual(3);
  });
});

describe("TraceView TRACE-007 Recent Traces (overall_risk_score field)", () => {
  it("reads overall_risk_score (0–1, scaled once) with the right threshold color", async () => {
    stubFetch(TIMELINE, AUDIT, true, { ok: true, items: [{ audit_id: "rrrr1111aaaa", overall_risk_score: 0.55 }] });
    render(<TraceView token="t" />);
    await waitFor(() => expect(screen.getByText("55")).toBeInTheDocument());
    expect(screen.getByText("55")).toHaveStyle({ color: "rgb(202, 138, 4)" }); // amber (>=40)
  });

  it("falls back to legacy risk_score and omits the number when score is null", async () => {
    stubFetch(TIMELINE, AUDIT, true, { ok: true, items: [
      { audit_id: "legacy0000aa", risk_score: 0.82 },     // legacy fallback -> 82
      { audit_id: "noscore0000a" },                         // no score -> no number, no NaN
    ] });
    render(<TraceView token="t" />);
    await waitFor(() => expect(screen.getByText("82")).toBeInTheDocument());
    expect(screen.queryByText("NaN")).not.toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows a distinct empty state vs an access failure", async () => {
    stubFetch(TIMELINE, AUDIT, true, { ok: true, items: [] });
    const { unmount } = render(<TraceView token="t" />);
    await waitFor(() => expect(screen.getByText(/No recent traces for this tenant/i)).toBeInTheDocument());
    unmount();

    stubFetch(TIMELINE, AUDIT, true, { ok: false, items: [] });
    render(<TraceView token="t" />);
    await waitFor(() => expect(screen.getByText(/Recent traces are unavailable/i)).toBeInTheDocument());
  });

  it("a recent-list failure leaves the rest of the page functional", async () => {
    stubFetch(TIMELINE, AUDIT, true, { ok: false, items: [] });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    // the main trace still loads despite the recent-list failure
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
  });
});

describe("TraceView TRACE-006 signed export actions", () => {
  let clickSpy;
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  function stubExport(exportResp) {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (url === "/api/v1/audit/audit-123456789/trace") {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(TIMELINE) });
      }
      if (url === "/api/v1/audits/audit-123456789") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(AUDIT) });
      }
      if (url.includes("/export/")) return Promise.resolve(exportResp);
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }));
  }

  it("downloads signed JSON with a client-derived filename", async () => {
    stubExport({ ok: true, status: 200, blob: () => Promise.resolve(new Blob(["{}"])), headers: { get: () => null } });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    screen.getByRole("button", { name: /Export JSON/i }).click();
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    const urls = fetch.mock.calls.map((c) => c[0]);
    expect(urls).toContain("/api/v1/audit/audit-123456789/export/json");
  });

  it("downloads signed PDF using the server-provided filename", async () => {
    stubExport({
      ok: true, status: 200,
      blob: () => Promise.resolve(new Blob(["%PDF"])),
      headers: { get: (h) => (h === "Content-Disposition" ? 'attachment; filename=saro-evidence-abcd1234.pdf' : null) },
    });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    screen.getByRole("button", { name: /Export PDF/i }).click();
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    const urls = fetch.mock.calls.map((c) => c[0]);
    expect(urls).toContain("/api/v1/audit/audit-123456789/export/pdf");
  });

  it("shows an inline error and saves nothing on a 403/404 export", async () => {
    stubExport({ ok: false, status: 403, blob: () => Promise.resolve(new Blob([])), headers: { get: () => null } });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    screen.getByRole("button", { name: /Export JSON/i }).click();
    await waitFor(() => expect(screen.getByText(/don't have access to export/i)).toBeInTheDocument());
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it("disables export actions when no trace is loaded", () => {
    stubExport({ ok: true, status: 200, blob: () => Promise.resolve(new Blob([])), headers: { get: () => null } });
    render(<TraceView token="t" />); // no initialAuditId -> no trace loaded
    expect(screen.queryByRole("button", { name: /Export JSON/i })).toBeNull();
  });
});

describe("TraceView TRACE-004 honest integrity banner", () => {
  it("shows a specific verified claim only when the backend confirms a real signature", async () => {
    stubFetch({ ...TIMELINE, integrity: { status: "verified", verified: true, export_hash: "9911aa22bb33", detail: "HMAC-SHA256 signature valid over the canonical export." } });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText(/Integrity verified/i)).toBeInTheDocument());
    expect(screen.getByText(/HMAC-SHA256 signature valid/i)).toBeInTheDocument();
    expect(screen.getByText(/9911aa22bb33/)).toBeInTheDocument();
  });

  it("shows a neutral 'not verified' state (never green 'verified') when unavailable", async () => {
    stubFetch({ ...TIMELINE, integrity: { status: "unavailable", verified: false, detail: "No signed export on record for this audit." } });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText(/Integrity not verified/i)).toBeInTheDocument());
    expect(screen.queryByText(/Integrity verified/i)).not.toBeInTheDocument();
  });

  it("makes no positive integrity claim when the backend returns no verdict", async () => {
    stubFetch({ ...TIMELINE, integrity: null });
    render(<TraceView token="t" initialAuditId="audit-123456789" />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    expect(screen.queryByText(/Integrity verified/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Integrity not verified/i)).not.toBeInTheDocument();
  });
});

describe("TraceView TRACE-005 ADR-004 methodology gate", () => {
  it("shows a How SARO Reasons affordance that navigates to the doc", async () => {
    const onNavigate = vi.fn();
    render(<TraceView token="t" onNavigate={onNavigate} />);
    const link = screen.getByText(/How SARO Reasons/i);
    link.click();
    expect(onNavigate).toHaveBeenCalledWith("how_saro_reasons");
  });

  it("gates technical mode for a demo session when the doc is not ready (default-deny)", async () => {
    const demoUser = { role: "demo_viewer", read_only: true };
    render(<TraceView token="t" initialAuditId="audit-123456789" user={demoUser} methodologyReady={false} />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    expect(screen.getByText(/transparency document is published/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Technical" })).toBeDisabled();
  });

  it("does NOT gate when the doc is ready", async () => {
    const demoUser = { role: "demo_viewer", read_only: true };
    render(<TraceView token="t" initialAuditId="audit-123456789" user={demoUser} methodologyReady={true} />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    expect(screen.queryByText(/transparency document is published/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Technical" })).not.toBeDisabled();
  });

  it("does NOT gate an internal (non-demo) session even when the doc is not ready", async () => {
    const internalUser = { role: "operator", persona_role: "ai_auditor" };
    render(<TraceView token="t" initialAuditId="audit-123456789" user={internalUser} methodologyReady={false} />);
    await waitFor(() => expect(screen.getByText("74/100")).toBeInTheDocument());
    expect(screen.queryByText(/transparency document is published/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Technical" })).not.toBeDisabled();
  });
});
