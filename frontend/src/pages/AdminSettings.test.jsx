/**
 * STORY-TAB-008 AC-1: Evaluations folded into Admin Settings.
 * The embedded component is the original Evaluations page (TAB-004 gating
 * unchanged), hosted as an "Evaluation Runs" section.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import AdminSettings from "./AdminSettings";

function stubFetch({ evals = [] } = {}) {
  vi.stubGlobal("fetch", vi.fn((url) => {
    const u = String(url);
    if (u.startsWith("/api/v1/evaluations")) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(evals) });
    }
    if (u.startsWith("/api/v1/auth/users")) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
  }));
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminSettings — STORY-TAB-008: Evaluation Runs section", () => {
  it("hosts the embedded Evaluations component (runs render)", async () => {
    stubFetch({ evals: [{ id: "r1", status: "completed", eval_type: "batch", datasets_passed: 4, datasets_attempted: 5 }] });
    render(<AdminSettings token="t" user={{ role: "admin", persona_role: "admin" }} />);
    expect(await screen.findByText("Evaluation Runs")).toBeInTheDocument();
    expect(await screen.findByText(/4\/5 datasets passed/)).toBeInTheDocument();
  });

  it("trigger button appears only for role=super_admin (TAB-004 gating intact in the new host)", async () => {
    stubFetch();
    render(<AdminSettings token="t" user={{ role: "admin", persona_role: "admin" }} />);
    await screen.findByText("Evaluation Runs");
    expect(screen.queryByRole("button", { name: /Trigger Eval Run/i })).not.toBeInTheDocument();
  });

  it("super_admin still gets the trigger button in the new host", async () => {
    stubFetch();
    render(<AdminSettings token="t" user={{ role: "super_admin", persona_role: "super_admin" }} />);
    expect(await screen.findByRole("button", { name: /Trigger Eval Run/i })).toBeInTheDocument();
  });
});
