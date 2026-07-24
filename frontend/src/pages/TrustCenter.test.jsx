import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TrustCenter from "./TrustCenter";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }))
  );
});

const LABELS = ["Governance Principles", "How SARO Reasons", "Claims Matrix", "DPA & Governance"];

describe("STORY-112: Trust Center consolidates the four governance pages", () => {
  it("renders all four governance sections as tabs", () => {
    render(<TrustCenter token="t" />);
    for (const label of LABELS) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument();
    }
  });

  it("defaults to the Governance Principles tab", () => {
    render(<TrustCenter token="t" />);
    expect(screen.getByRole("tab", { name: "Governance Principles" })).toHaveAttribute("aria-selected", "true");
  });

  it("opens the tab named by initialTab (preserves deep-link target)", () => {
    render(<TrustCenter token="t" initialTab="claims_matrix" />);
    expect(screen.getByRole("tab", { name: "Claims Matrix" })).toHaveAttribute("aria-selected", "true");
  });

  it("switches sections on tab click", async () => {
    const user = userEvent.setup();
    render(<TrustCenter token="t" />);
    await user.click(screen.getByRole("tab", { name: "DPA & Governance" }));
    expect(screen.getByRole("tab", { name: "DPA & Governance" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("STORY-TAB-008 AC-6: detection-quality evidence card", () => {
  const RUN = {
    id: "r1", status: "completed", datasets_passed: 5, datasets_attempted: 5,
    total_samples_uploaded: 800, completed_at: "2026-07-20T10:00:00Z",
  };

  function stubEvalList(json, ok = true) {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).startsWith("/api/v1/evaluations")) {
        return Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(json) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }));
  }

  it("renders the latest completed run for an admin account role", async () => {
    stubEvalList([RUN]);
    render(<TrustCenter token="t" user={{ role: "admin", persona_role: "admin" }} />);
    expect(await screen.findByText("Detection quality evidence")).toBeInTheDocument();
    expect(screen.getByText(/5\/5 datasets passed/)).toBeInTheDocument();
    expect(screen.getByText(/800 samples/)).toBeInTheDocument();
    // evidence language, no certification claim
    expect(screen.getByText(/human review required/i)).toBeInTheDocument();
  });

  it("renders no card and never fetches for a role the backend would 403", async () => {
    stubEvalList([RUN]);
    render(<TrustCenter token="t" user={{ role: "viewer", persona_role: "compliance_lead" }} />);
    expect(screen.getByRole("tab", { name: "Governance Principles" })).toBeInTheDocument();
    expect(screen.queryByText("Detection quality evidence")).not.toBeInTheDocument();
    expect(fetch.mock.calls.map((c) => String(c[0])).some((u) => u.startsWith("/api/v1/evaluations"))).toBe(false);
  });

  it("renders no card when there is no completed run (fail-silent, no fabricated evidence)", async () => {
    stubEvalList([]);
    render(<TrustCenter token="t" user={{ role: "super_admin" }} />);
    expect(screen.getByRole("tab", { name: "Governance Principles" })).toBeInTheDocument();
    expect(screen.queryByText("Detection quality evidence")).not.toBeInTheDocument();
  });
});
