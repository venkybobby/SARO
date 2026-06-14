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
