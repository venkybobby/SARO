/**
 * STORY-TAB-002 / FND-075 — Onboarding tab renders the backend checklist.
 *
 * Contract pinned (routers/onboarding.py):
 *   GET /api/v1/onboarding/status →
 *     {tenant_id, completed_steps, total_steps, completion_pct,
 *      onboarding_complete, steps:[{key,label,completed,cta_url}]}
 *
 * Pre-fix, the page hardcoded 7 step ids the API never returns and read flat
 * booleans → permanently 0% with 7 unchecked steps.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Onboarding from "./Onboarding";

const STATUS = {
  tenant_id: "c4dc0d5a-481b-47d1-bddc-90f15e841130",
  completed_steps: 2,
  total_steps: 4,
  completion_pct: 50,
  onboarding_complete: false,
  steps: [
    { key: "profile",    label: "Complete tenant profile",                          completed: true,  cta_url: "/api/v1/clients/me" },
    { key: "first_scan", label: "Run your first risk scan",                         completed: false, cta_url: "/api/v1/scan" },
    { key: "aims_doc",   label: "Register an AI model in the AIMS document library", completed: true,  cta_url: "/api/v1/aims/documents" },
    { key: "sso",        label: "Configure SAML 2.0 SSO (optional)",                completed: false, cta_url: "/api/v1/sso/configure" },
  ],
};

function ok(json) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(json) });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-002 AC-1 / FND-075: API steps render, hardcoded list gone", () => {
  it("renders exactly the API's steps with their labels, checked iff completed", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(STATUS)));
    render(<Onboarding token="t" tenantId="tid" />);

    expect(await screen.findByText("Complete tenant profile")).toBeInTheDocument();
    expect(screen.getByText("Run your first risk scan")).toBeInTheDocument();
    expect(screen.getByText("Register an AI model in the AIMS document library")).toBeInTheDocument();
    expect(screen.getByText("Configure SAML 2.0 SSO (optional)")).toBeInTheDocument();
    // the old hardcoded labels must be gone
    expect(screen.queryByText("Tenant Created")).not.toBeInTheDocument();
    expect(screen.queryByText("Users Invited")).not.toBeInTheDocument();
    // completion marks: 2 done, 2 not
    expect(screen.getAllByText("✓")).toHaveLength(2);
  });

  it("AC-2: progress derives from API fields, not a local list", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(STATUS)));
    render(<Onboarding token="t" tenantId="tid" />);
    expect(await screen.findByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/2\/4 steps complete/)).toBeInTheDocument();
  });

  it("AC-3: onboarding_complete renders the completion banner", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({
      ...STATUS,
      completed_steps: 4, completion_pct: 100, onboarding_complete: true,
      steps: STATUS.steps.map((s) => ({ ...s, completed: true })),
    })));
    render(<Onboarding token="t" tenantId="tid" />);
    expect(await screen.findByText(/Onboarding complete/i)).toBeInTheDocument();
  });
});

describe("STORY-TAB-002 AC-4: in-app CTAs only where a mapping exists", () => {
  it("first_scan gets a Go button that navigates to upload; profile/sso get none", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    vi.stubGlobal("fetch", vi.fn(() => ok(STATUS)));
    render(<Onboarding token="t" tenantId="tid" onNavigate={onNavigate} />);

    await screen.findByText("Run your first risk scan");
    const buttons = screen.getAllByRole("button", { name: /Go/i });
    // only first_scan is incomplete AND mapped (aims_doc is mapped but completed)
    expect(buttons).toHaveLength(1);
    await user.click(buttons[0]);
    expect(onNavigate).toHaveBeenCalledWith("upload");
  });

  it("renders no raw /api/v1 hrefs", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(STATUS)));
    const { container } = render(<Onboarding token="t" tenantId="tid" />);
    await screen.findByText("Complete tenant profile");
    expect(container.querySelector('a[href^="/api/"]')).toBeNull();
  });
});

describe("STORY-TAB-002 AC-5 + edge cases", () => {
  it("non-2xx renders an error state, never a fake 0% checklist", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    render(<Onboarding token="t" tenantId="tid" />);
    expect(await screen.findByText(/Failed to load onboarding status/i)).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });

  it("empty steps array renders a neutral message, no divide-by-zero", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({
      tenant_id: "x", completed_steps: 0, total_steps: 0, completion_pct: 0,
      onboarding_complete: false, steps: [],
    })));
    render(<Onboarding token="t" tenantId="tid" />);
    expect(await screen.findByText(/No onboarding steps/i)).toBeInTheDocument();
  });

  it("unknown future step keys still render from their label (data-driven)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({
      ...STATUS,
      steps: [...STATUS.steps, { key: "future_thing", label: "A future step", completed: false, cta_url: null }],
    })));
    render(<Onboarding token="t" tenantId="tid" />);
    expect(await screen.findByText("A future step")).toBeInTheDocument();
  });
});
