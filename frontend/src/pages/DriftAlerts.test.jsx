/**
 * STORY-TAB-005 / FND-080 — Drift Alerts renders the real drift response.
 *
 * Contract pinned (routers/rule_packs.py GET /api/v1/rules/drift-alerts):
 *   {alerts:[{framework, current_version, latest_version, alert_type, message}],
 *    alert_count, current_versions:{fw:ver}, latest_known_versions:{fw:ver},
 *    checked_at}
 *
 * Pre-fix the page read data.framework_versions (an array key the API never
 * returns) so the "Current Framework Versions" grid never rendered, and alert
 * cards referenced what_changed/affected_rule_packs which have never existed.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import DriftAlerts from "./DriftAlerts";

const RESPONSE_NO_DRIFT = {
  alerts: [],
  alert_count: 0,
  current_versions: { "NIST-AI-RMF": "1.0.0", "EU-AI-ACT-2024": "1.0.0" },
  latest_known_versions: {
    "NIST-AI-RMF": "1.0.0",
    "EU-AI-ACT-2024": "1.0.0",
    "AIGP": "2.0.0",
    "ISO-42001": "2023.0",
  },
  checked_at: "2026-07-23T20:39:34.641780",
};

const RESPONSE_WITH_DRIFT = {
  alerts: [
    {
      framework: "NIST-AI-RMF",
      current_version: "1.0.0",
      latest_version: "2.0.0",
      alert_type: "version_drift",
      message: "NIST-AI-RMF has updated to 2.0.0 (you have 1.0.0)",
    },
  ],
  alert_count: 1,
  current_versions: { "NIST-AI-RMF": "1.0.0", "LEGACY-FW": "0.9.0" },
  latest_known_versions: { "NIST-AI-RMF": "2.0.0" },
  checked_at: "2026-07-23T20:39:34.641780",
};

function ok(json) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(json) });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-005 AC-1 / FND-080: version grid renders from the real keys", () => {
  it("one card per tracked framework; packless frameworks say so instead of vanishing", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(RESPONSE_NO_DRIFT)));
    render(<DriftAlerts token="t" />);

    expect(await screen.findByText("NIST-AI-RMF")).toBeInTheDocument();
    expect(screen.getByText("EU-AI-ACT-2024")).toBeInTheDocument();
    expect(screen.getByText("AIGP")).toBeInTheDocument();
    expect(screen.getByText("ISO-42001")).toBeInTheDocument();
    // AIGP + ISO-42001 are tracked but have no active pack
    expect(screen.getAllByText(/no pack/i)).toHaveLength(2);
  });

  it("shows the latest version when it differs from the pack's current one", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(RESPONSE_WITH_DRIFT)));
    render(<DriftAlerts token="t" />);
    expect(await screen.findByText(/Latest: 2\.0\.0/)).toBeInTheDocument();
  });

  it("edge: a framework with a pack but absent from latest_known_versions still renders", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(RESPONSE_WITH_DRIFT)));
    render(<DriftAlerts token="t" />);
    expect(await screen.findByText("LEGACY-FW")).toBeInTheDocument();
  });
});

describe("STORY-TAB-005 AC-2: alert cards render only real fields", () => {
  it("renders the alert message; no what-changed/affected-packs sections", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(RESPONSE_WITH_DRIFT)));
    render(<DriftAlerts token="t" />);
    expect(await screen.findByText(/NIST-AI-RMF has updated to 2\.0\.0/)).toBeInTheDocument();
    expect(screen.queryByText(/What Changed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Affected Rule Packs/)).not.toBeInTheDocument();
  });
});

describe("STORY-TAB-005 AC-3/AC-4: no-drift freshness and error handling", () => {
  it("the no-drift state carries checked_at so the green claim is evidently fresh", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(RESPONSE_NO_DRIFT)));
    render(<DriftAlerts token="t" />);
    expect(await screen.findByText(/No drift alerts/)).toBeInTheDocument();
    expect(screen.getByText(/Last checked: 2026-07-23/)).toBeInTheDocument();
  });

  it("a failed fetch renders the error banner and never the green no-drift state", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    render(<DriftAlerts token="t" />);
    expect(await screen.findByText(/Could not reach drift-check endpoint/)).toBeInTheDocument();
    expect(screen.queryByText(/No drift alerts/)).not.toBeInTheDocument();
  });

  it("edge: empty version maps render a neutral empty state, not a blank section", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({ alerts: [], alert_count: 0, current_versions: {}, latest_known_versions: {}, checked_at: "2026-07-23T20:00:00" })));
    render(<DriftAlerts token="t" />);
    expect(await screen.findByText(/No tracked framework versions/i)).toBeInTheDocument();
  });
});
