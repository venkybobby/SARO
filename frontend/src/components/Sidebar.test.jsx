/**
 * STORY-412: demo surface trim.
 *  - AC-2: a demo session (role === "demo_viewer") renders exactly DEMO_TABS,
 *    regardless of persona — no AIMS, Evaluations, Trust Center, Upload,
 *    Onboarding, or admin tabs.
 *  - AC-3: the persona switcher is never rendered for a demo session.
 *  - AC-5: non-demo persona tab sets are unchanged (regression snapshot).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DEMO_TABS from "../config/demoTabs.json";
import Sidebar from "./Sidebar";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ db_ok: true }) })));
});
afterEach(() => vi.unstubAllGlobals());

const TAB_LABELS = {
  dashboard:        "Dashboard",
  compliance_hub:   "Compliance Hub",
  trace_view:       "TRACE View",
  trust_center:     "Trust Center",
  rule_packs:       "Rule Packs",
  coverage_gap:     "Coverage Gap",
  remediation:      "Remediation",
  drift_alerts:     "Drift Alerts",
  onboarding:       "Onboarding",
  upload:           "Upload & Scan",
  admin_settings:   "Admin Settings",
  aims:             "AIMS",
  evaluations:      "Evaluations",
  evf_admin:        "EVF Status",
  risk_register:    "Risk Register",
  ai_insights:      "AI Insights",
  reports:          "Reports",
  settings:         "Settings",
  knowledge_portal: "Knowledge Portal",
};

const OFF_WHITELIST_LABELS = [
  "AIMS", "Evaluations", "Trust Center", "Upload & Scan", "Onboarding", "Admin Settings",
];

describe("Sidebar — STORY-412 AC-2: demo session renders exactly DEMO_TABS", () => {
  it("shows every DEMO_TABS entry and nothing off the whitelist, for a demo_viewer with no persona_role", () => {
    render(<Sidebar user={{ role: "demo_viewer" }} activePage="dashboard" onNavigate={() => {}} />);
    for (const tab of DEMO_TABS) {
      expect(screen.getByText(TAB_LABELS[tab])).toBeTruthy();
    }
    for (const label of OFF_WHITELIST_LABELS) {
      expect(screen.queryByText(label)).toBeNull();
    }
  });

  it("still shows exactly DEMO_TABS even when persona_role is compliance_lead (whose full PERSONA_TABS list is much larger)", () => {
    render(<Sidebar user={{ role: "demo_viewer", persona_role: "compliance_lead" }} activePage="dashboard" onNavigate={() => {}} />);
    for (const tab of DEMO_TABS) {
      expect(screen.getByText(TAB_LABELS[tab])).toBeTruthy();
    }
    for (const label of OFF_WHITELIST_LABELS) {
      expect(screen.queryByText(label)).toBeNull();
    }
  });
});

describe("Sidebar — STORY-412 AC-3: persona switcher hidden for demo sessions", () => {
  it("clicking the user block never opens the switcher for role=demo_viewer", () => {
    render(<Sidebar user={{ role: "demo_viewer", persona_role: "compliance_lead", email: "demo@saro.io" }} activePage="dashboard" onNavigate={() => {}} />);
    fireEvent.click(screen.getByText("demo@saro.io"));
    expect(screen.queryByText("Switch persona")).toBeNull();
  });
});

describe("Sidebar — STORY-412 AC-5: non-demo tab sets unchanged", () => {
  const PERSONA_EXPECTED = {
    compliance_lead: ["Dashboard", "Compliance Hub", "TRACE View", "Trust Center", "AIMS", "Onboarding", "Upload & Scan", "Evaluations", "Reports"],
    risk_officer:    ["Dashboard", "Risk Register", "TRACE View", "AI Insights", "Reports"],
    ai_auditor:      ["Dashboard", "TRACE View", "Rule Packs", "Coverage Gap", "Remediation", "Drift Alerts", "Upload & Scan", "Knowledge Portal"],
    operator:        ["Dashboard", "Upload & Scan", "TRACE View", "Remediation", "Knowledge Portal"],
    admin: ["Dashboard", "Compliance Hub", "TRACE View", "Trust Center", "Rule Packs", "Coverage Gap",
            "Remediation", "Drift Alerts", "AIMS", "Onboarding", "Upload & Scan", "Admin Settings",
            "Evaluations", "EVF Status", "Risk Register", "AI Insights", "Reports", "Settings",
            "Knowledge Portal"],
    super_admin: ["Dashboard", "Compliance Hub", "TRACE View", "Trust Center", "Rule Packs", "Coverage Gap",
                  "Remediation", "Drift Alerts", "AIMS", "Onboarding", "Upload & Scan", "Admin Settings",
                  "Evaluations", "Risk Register", "AI Insights", "Reports", "Settings"],
  };

  for (const [persona, expectedLabels] of Object.entries(PERSONA_EXPECTED)) {
    it(`${persona} still sees exactly its pre-STORY-412 tab set`, () => {
      render(<Sidebar user={{ role: persona, persona_role: persona }} activePage="dashboard" onNavigate={() => {}} />);
      for (const label of expectedLabels) {
        expect(screen.getByText(label)).toBeTruthy();
      }
      // None of the demo-only-adjacent labels beyond this persona's own set leak in.
      const allTabButtons = screen.getAllByRole("button").map((b) => b.textContent);
      const shown = allTabButtons.filter((t) => Object.values(TAB_LABELS).some((l) => t.includes(l)));
      expect(shown.length).toBe(expectedLabels.length);
    });
  }

  it("admin's switcher still opens on click (positive control — canSwitch is keyed off role, unaffected by STORY-412)", () => {
    render(<Sidebar user={{ role: "admin", persona_role: "admin", email: "admin@saro.io" }} activePage="dashboard" onNavigate={() => {}} />);
    expect(screen.queryByText("Switch persona")).toBeNull(); // closed by default
    fireEvent.click(screen.getByText("admin@saro.io"));
    expect(screen.getByText("Switch persona")).toBeTruthy(); // opens for a switchable role
  });
});
