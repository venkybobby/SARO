/**
 * STORY-412 (round 2 — reviewer REQUEST CHANGES): DEMO_TABS only filtered
 * Sidebar's own button list; any page could still call onNavigate(page)
 * directly and AppShell would happily render an off-whitelist page, which
 * then 403s on its own fetches (reproduced via TraceView's "How SARO
 * Reasons" link → Trust Center → a super_admin/operator-only endpoint).
 * The fix lives in AppShell.navigateNow, the one place all navigation flows
 * through — this pins it directly, independent of which page happens to
 * expose the off-whitelist link today.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../pages/Dashboard", () => ({
  default: ({ onNavigate }) => (
    <div>
      <span>Dashboard content</span>
      <button onClick={() => onNavigate?.("upload")}>Go off-whitelist</button>
      <button onClick={() => onNavigate?.("trace_view")}>Go on-whitelist</button>
    </div>
  ),
}));
vi.mock("../pages/Upload", () => ({ default: () => <div>Upload page content</div> }));
vi.mock("../pages/TraceView", () => ({ default: () => <div>TraceView page content</div> }));

import AppShell from "./AppShell";

const TOAST = { success: () => {}, error: () => {} };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ db_ok: true }) })));
});
afterEach(() => vi.unstubAllGlobals());

describe("AppShell — STORY-412: navigation guard for demo sessions", () => {
  it("ignores an off-whitelist onNavigate call for role=demo_viewer", async () => {
    render(<AppShell token="t" user={{ role: "demo_viewer", persona_role: "compliance_lead" }} onSignOut={() => {}} onUserUpdate={() => {}} toast={TOAST} />);
    await waitFor(() => expect(screen.getByText("Dashboard content")).toBeTruthy());
    fireEvent.click(screen.getByText("Go off-whitelist"));
    expect(screen.queryByText("Upload page content")).toBeNull();
    expect(screen.getByText("Dashboard content")).toBeTruthy();
  });

  it("still allows navigation to an on-whitelist page for role=demo_viewer", async () => {
    render(<AppShell token="t" user={{ role: "demo_viewer", persona_role: "compliance_lead" }} onSignOut={() => {}} onUserUpdate={() => {}} toast={TOAST} />);
    await waitFor(() => expect(screen.getByText("Dashboard content")).toBeTruthy());
    fireEvent.click(screen.getByText("Go on-whitelist"));
    await waitFor(() => expect(screen.getByText("TraceView page content")).toBeTruthy());
  });

  it("a non-demo user can still navigate anywhere — guard is demo-only (regression)", async () => {
    render(<AppShell token="t" user={{ role: "operator", persona_role: "operator" }} onSignOut={() => {}} onUserUpdate={() => {}} toast={TOAST} />);
    await waitFor(() => expect(screen.getByText("Dashboard content")).toBeTruthy());
    fireEvent.click(screen.getByText("Go off-whitelist"));
    await waitFor(() => expect(screen.getByText("Upload page content")).toBeTruthy());
  });
});

/**
 * STORY-TAB-002 / FND-075 — OnboardingWizard shares the Onboarding tab's
 * contract bug: it hardcoded 7 step ids and read flat booleans from
 * GET /api/v1/onboarding/status, which returns
 * {steps:[{key,label,completed,cta_url}], completed_steps, total_steps,
 *  completion_pct, onboarding_complete} — so every first login showed 0/7.
 */
const ONBOARDING_STATUS = {
  tenant_id: "tid",
  completed_steps: 2,
  total_steps: 4,
  completion_pct: 50,
  onboarding_complete: false,
  steps: [
    { key: "profile",    label: "Complete tenant profile",  completed: true,  cta_url: "/api/v1/clients/me" },
    { key: "first_scan", label: "Run your first risk scan", completed: false, cta_url: "/api/v1/scan" },
    { key: "aims_doc",   label: "Register an AI model in the AIMS document library", completed: true, cta_url: "/api/v1/aims/documents" },
    { key: "sso",        label: "Configure SAML 2.0 SSO (optional)", completed: false, cta_url: "/api/v1/sso/configure" },
  ],
};

describe("AppShell — STORY-TAB-002 / FND-075: OnboardingWizard binds the real contract", () => {
  beforeEach(() => {
    localStorage.removeItem("saro_onboarding_dismissed");
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/api/v1/onboarding/status")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(ONBOARDING_STATUS) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ db_ok: true }) });
    }));
  });
  afterEach(() => localStorage.removeItem("saro_onboarding_dismissed"));

  it("first-login wizard shows API progress and API step labels, not 0/7 hardcoded ones", async () => {
    render(<AppShell token="t" user={{ role: "admin", persona_role: "admin" }} onSignOut={() => {}} onUserUpdate={() => {}} toast={TOAST} />);
    expect(await screen.findByText(/2\/4 steps complete/)).toBeTruthy();
    expect(screen.getByText("Run your first risk scan")).toBeTruthy();
    expect(screen.queryByText("Tenant Created")).toBeNull();
    expect(screen.queryByText(/0\/7 steps complete/)).toBeNull();
  });

  it("wizard Go on first_scan dismisses and navigates to Upload", async () => {
    render(<AppShell token="t" user={{ role: "admin", persona_role: "admin" }} onSignOut={() => {}} onUserUpdate={() => {}} toast={TOAST} />);
    await screen.findByText("Run your first risk scan");
    const goButtons = screen.getAllByText(/Go →/);
    expect(goButtons).toHaveLength(1); // only first_scan: incomplete AND mapped
    fireEvent.click(goButtons[0]);
    await waitFor(() => expect(screen.getByText("Upload page content")).toBeTruthy());
  });

  it("wizard fetch failure shows a neutral line, never fake progress", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/api/v1/onboarding/status")) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ db_ok: true }) });
    }));
    render(<AppShell token="t" user={{ role: "admin", persona_role: "admin" }} onSignOut={() => {}} onUserUpdate={() => {}} toast={TOAST} />);
    expect(await screen.findByText(/Couldn.t load setup progress/i)).toBeTruthy();
    expect(screen.queryByText(/steps complete/)).toBeNull();
  });
});
