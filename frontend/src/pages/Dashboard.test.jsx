import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
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

const COVERAGE = { overall_coverage_pct: 82.5, framework_count: 4, total_rules: 40 };
const AUDITS_PAGE = [
  { id: "1", created_at: new Date().toISOString() },
  { id: "2", created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString() },
  { id: "3", created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString() }, // outside the 7d window
];

function routedFetch(url) {
  if (url.includes("/risk/summary")) return Promise.resolve({ ok: true, json: () => Promise.resolve(SUMMARY) });
  if (url.includes("/risk/whats-changed")) return Promise.resolve({ ok: true, json: () => Promise.resolve(WHATS_CHANGED) });
  if (url.includes("/compliance-matrix/coverage")) return Promise.resolve({ ok: true, json: () => Promise.resolve(COVERAGE) });
  if (url.includes("/audits")) return Promise.resolve({ ok: true, json: () => Promise.resolve(AUDITS_PAGE) });
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

describe("Dashboard — STORY-413: no placeholder KPI tiles", () => {
  it("AC-1: no fabricated tile values render (Controls Overdue, Readiness %, etc.)", async () => {
    render(<Dashboard token="t" user={{ persona_role: "compliance_lead" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Risk Posture")).toBeTruthy());
    expect(screen.queryByText("Controls Overdue")).toBeNull();
    expect(screen.queryByText("Readiness %")).toBeNull();
    expect(screen.queryByText(/sample — not yet wired to live data/i)).toBeNull();
  });

  it("AC-1: source no longer contains a placeholder mechanism or the stale caption", () => {
    expect(SOURCE).not.toMatch(/placeholder\s*:\s*true/);
    expect(SOURCE).not.toMatch(/sample — not yet wired to live data/);
  });

  it("AC-2: Audits (7d) and Coverage % render live values from their endpoints, for demo and operator personas", async () => {
    render(<Dashboard token="t" user={{ persona_role: "compliance_lead" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Audits (7d)")).toBeTruthy());
    expect(screen.getByText("Coverage %")).toBeTruthy();
    // AUDITS_PAGE has 2 of 3 records inside the 7-day window.
    await waitFor(() => expect(screen.getByText("2")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("82.5%")).toBeTruthy());
  });

  it("AC-2: operator persona also gets both live tiles", async () => {
    render(<Dashboard token="t" user={{ persona_role: "operator" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Audits (7d)")).toBeTruthy());
    expect(screen.getByText("Coverage %")).toBeTruthy();
  });

  it("FND-052: operator persona never renders the fake 'Avg Score' tile", async () => {
    render(<Dashboard token="t" user={{ persona_role: "operator" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Scans Today")).toBeTruthy());
    expect(screen.queryByText("Avg Score")).toBeNull();
  });

  it("AC-3: a failed Coverage % fetch renders an explicit Unavailable state, never a stale/default number", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/compliance-matrix/coverage")) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      }
      return routedFetch(String(url));
    }));
    render(<Dashboard token="t" user={{ persona_role: "compliance_lead" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Coverage %")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("Unavailable")).toBeTruthy());
  });

  it("AC-3: a failed Audits (7d) fetch renders Unavailable, not zero (zero would look like a real measurement)", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/audits")) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      }
      return routedFetch(String(url));
    }));
    render(<Dashboard token="t" user={{ persona_role: "compliance_lead" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Audits (7d)")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("Unavailable")).toBeTruthy());
  });
});

/** The KpiCard container for a given label — label span's grandparent
 * (span -> header row div -> card div, per KpiCard's render structure). */
function kpiCard(label) {
  return screen.getByText(label).parentElement.parentElement;
}

describe("Dashboard — STORY-413 round 2: deriveKpis index mapping is correct, not just present", () => {
  // Reviewer-caught gap: page-wide presence assertions pass even if deriveKpis writes the
  // live value into the wrong array slot (a swapped-index bug) — the swapped value still
  // renders SOMEWHERE on the page, just under the wrong label, and an unscoped
  // queryByText(wrongValue) check can false-fail against a DIFFERENT tile that legitimately
  // shows that value. These scope every assertion to the specific tile's own card via
  // `within()`, so a swap is caught regardless of what else renders elsewhere on the page.
  it("compliance_lead: 'Scans This Week' shows the live audit_count (5), not the static default (12)", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/risk/summary")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ...SUMMARY, audit_count: 5 }) });
      }
      return routedFetch(String(url));
    }));
    render(<Dashboard token="t" user={{ persona_role: "compliance_lead" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Scans This Week")).toBeTruthy());
    const card = kpiCard("Scans This Week");
    await waitFor(() => expect(within(card).getByText("5")).toBeTruthy());
    expect(within(card).queryByText("12")).toBeNull();
  });

  it("risk_officer: 'Critical Risks' shows critical_findings_count (3), not the static default (12) or remediation_pct (40%)", async () => {
    render(<Dashboard token="t" user={{ persona_role: "risk_officer" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Critical Risks")).toBeTruthy());
    const card = kpiCard("Critical Risks");
    await waitFor(() => expect(within(card).getByText("3")).toBeTruthy());
    expect(within(card).queryByText("12")).toBeNull();
    expect(within(card).queryByText("40%")).toBeNull();
  });

  it("risk_officer: 'Remediation %' shows remediation_pct (40%), not the static default (54%) or critical_findings_count (3)", async () => {
    render(<Dashboard token="t" user={{ persona_role: "risk_officer" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Remediation %")).toBeTruthy());
    const card = kpiCard("Remediation %");
    await waitFor(() => expect(within(card).getByText("40%")).toBeTruthy());
    expect(within(card).queryByText("54%")).toBeNull();
    expect(within(card).queryByText("3")).toBeNull();
  });

  it("ai_auditor: 'Scans Today' shows the live audit_count (9), not the static default (7)", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/risk/summary")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ...SUMMARY, audit_count: 9 }) });
      }
      return routedFetch(String(url));
    }));
    render(<Dashboard token="t" user={{ persona_role: "ai_auditor" }} onNavigate={() => {}} />);
    await waitFor(() => expect(screen.getByText("Scans Today")).toBeTruthy());
    const card = kpiCard("Scans Today");
    await waitFor(() => expect(within(card).getByText("9")).toBeTruthy());
    expect(within(card).queryByText("7")).toBeNull();
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
