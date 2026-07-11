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
