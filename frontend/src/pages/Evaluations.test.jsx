/**
 * STORY-TAB-004 — Evaluations page gating matches the backend RBAC.
 *
 * Backend gates (routers/evaluations.py):
 *   GET  /api/v1/evaluations         require_role("super_admin","operator","admin")
 *   POST /api/v1/evaluations/trigger require_role("super_admin")
 * require_role checks the ACCOUNT role (auth.py) — so the page must key off
 * user.role, never persona_role. Pre-fix the trigger button rendered for the
 * ai_auditor/admin *personas*, whose accounts the backend rejects.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Evaluations from "./Evaluations";

function ok(json) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(json) });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-004 AC-3: trigger button keyed off account role", () => {
  it("renders for role=super_admin even when persona-switched to compliance_lead", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok([])));
    render(<Evaluations token="t" user={{ role: "super_admin", persona_role: "compliance_lead" }} />);
    expect(await screen.findByRole("button", { name: /Trigger Eval Run/i })).toBeInTheDocument();
  });

  it("does NOT render for role=admin (backend trigger gate would 403)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok([])));
    render(<Evaluations token="t" user={{ role: "admin", persona_role: "admin" }} />);
    await screen.findByText(/No evaluation runs yet/);
    expect(screen.queryByRole("button", { name: /Trigger Eval Run/i })).not.toBeInTheDocument();
  });

  it("does NOT render for an ai_auditor persona on an unprivileged role (pre-fix bug)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok([])));
    render(<Evaluations token="t" user={{ role: "viewer", persona_role: "ai_auditor" }} />);
    await screen.findByText(/No evaluation runs yet/);
    expect(screen.queryByRole("button", { name: /Trigger Eval Run/i })).not.toBeInTheDocument();
  });

  it("edge: missing user renders no trigger button and doesn't crash", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok([])));
    render(<Evaluations token="t" />);
    await screen.findByText(/No evaluation runs yet/);
    expect(screen.queryByRole("button", { name: /Trigger Eval Run/i })).not.toBeInTheDocument();
  });
});

describe("STORY-TAB-004 AC-4: 403 renders an access explanation, not a bare code", () => {
  it("explains the role restriction on 403", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 403, json: () => Promise.resolve({}) })));
    render(<Evaluations token="t" user={{ role: "viewer", persona_role: "compliance_lead" }} />);
    expect(await screen.findByText(/Your role does not have access to evaluation runs/)).toBeInTheDocument();
    expect(screen.queryByText(/^⚠ 403$/)).not.toBeInTheDocument();
  });

  it("non-403 errors keep the generic banner", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    render(<Evaluations token="t" user={{ role: "admin" }} />);
    expect(await screen.findByText(/⚠ 500/)).toBeInTheDocument();
  });
});
