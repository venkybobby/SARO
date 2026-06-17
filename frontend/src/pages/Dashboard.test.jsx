import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import Dashboard from "./Dashboard";

const SOURCE_PATH = path.resolve(__dirname, "./Dashboard.jsx");
const SOURCE = readFileSync(SOURCE_PATH, "utf-8");

const SUMMARY = {
  rag_status: "AMBER",
  overall_risk_score: 63,
  open_findings_count: 7,
  critical_findings_count: 3,
  top_findings: [{ id: "1" }, { id: "2" }],
  remediation_pct: 40,
  audit_count: 12,
  generated_at: "2026-06-17T10:00:00",
};

const WHATS_CHANGED = {
  current_avg_score: 63,
  score_delta: 5,
  delta_direction: "up",
  new_audits_count: 3,
};

function routedFetch(url) {
  if (url.includes("/risk/summary")) return Promise.resolve({ ok: true, json: () => Promise.resolve(SUMMARY) });
  if (url.includes("/risk/whats-changed")) return Promise.resolve({ ok: true, json: () => Promise.resolve(WHATS_CHANGED) });
  return Promise.resolve({ ok: true, json: () => Promise.resolve([]) }); // drift-alerts etc.
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url) => routedFetch(String(url))));
});
afterEach(() => vi.unstubAllGlobals());

describe("Dashboard — FND-021: duplicate Quick Actions block removed", () => {
  it("renders the primary action exactly once", async () => {
    render(<Dashboard token="t" user={{ persona_role: "risk_officer" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Risk Posture")).toBeTruthy());
    expect(screen.getAllByText("Open Risk Register")).toHaveLength(1);
    expect(screen.getAllByText("View Recent TRACE")).toHaveLength(1);
  });

  it("source contains the Quick Actions buttons only once (no copy-paste block)", () => {
    const matches = SOURCE.match(/Open Risk Register/g) || [];
    expect(matches).toHaveLength(1);
  });
});

describe("Dashboard — FND-022: posture banner labels match their data", () => {
  it("shows Risk Score (overall_risk_score) and Open Risks (open_findings_count)", async () => {
    render(<Dashboard token="t" user={{ persona_role: "risk_officer" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Risk Score")).toBeTruthy());
    expect(screen.getByText("Open Risks")).toBeTruthy();
    expect(screen.getAllByText("63").length).toBeGreaterThanOrEqual(1);  // overall_risk_score
    expect(screen.getAllByText("7").length).toBeGreaterThanOrEqual(1);    // open_findings_count
  });

  it("banner no longer maps audit_count to 'Open Risks' nor renders an 'Overdue' stat", () => {
    expect(SOURCE).toMatch(/openRisks:\s*data\.open_findings_count/);
    expect(SOURCE).toMatch(/riskScore:\s*data\.overall_risk_score/);
    // The misleading always-zero "Overdue" banner stat is gone.
    expect(SOURCE).not.toMatch(/overdue:\s*data\.top_findings/i);
  });
});

describe("Dashboard — FND-023: fabricated KPI deltas removed, real trend wired", () => {
  it("renders no fabricated 'since last period' delta text", async () => {
    render(<Dashboard token="t" user={{ persona_role: "risk_officer" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Risk Posture")).toBeTruthy());
    expect(screen.queryByText(/since last period/i)).toBeNull();
  });

  it("renders the real 7-day trend backed by /risk/whats-changed", async () => {
    render(<Dashboard token="t" user={{ persona_role: "risk_officer" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText(/7-day avg risk score/i)).toBeTruthy());
  });

  it("PERSONA_KPIS no longer hardcodes delta literals", () => {
    expect(SOURCE).not.toMatch(/delta:\s*[+-]?\d/);
    expect(SOURCE).not.toMatch(/since last period/);
  });
});

describe("Dashboard — empty/first-run state (P2)", () => {
  it("shows a first-run empty state when there are no audits", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/risk/summary")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ...SUMMARY, audit_count: 0, open_findings_count: 0 }) });
      }
      return routedFetch(String(url));
    }));
    render(<Dashboard token="t" user={{ persona_role: "operator" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("No audits yet")).toBeTruthy());
  });
});
