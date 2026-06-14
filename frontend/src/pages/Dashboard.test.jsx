import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Dashboard from "./Dashboard";

beforeEach(() => {
  // Dashboard fetches several endpoints on mount; a permissive catch-all is enough.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }))
  );
});

describe("Dashboard quick actions (regression: duplicated Quick Actions block)", () => {
  it("renders the persona quick-actions row exactly once (no duplicate buttons)", async () => {
    render(<Dashboard token="t" user={{ persona_role: "admin" }} onNavigate={() => {}} />);

    // The duplicated block previously rendered each of these twice.
    expect(await screen.findAllByText("View Recent TRACE")).toHaveLength(1);
    expect(screen.getAllByText("Open Risk Register")).toHaveLength(1);
  });
});
