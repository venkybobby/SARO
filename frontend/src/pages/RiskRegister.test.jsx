import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskRegister from "./RiskRegister";

const RISK = {
  id: "RISK-1", title: "Test risk", owner: "alice", category: "AI Quality",
  severity: "high", status: "Open", dueDate: "2026-12-01",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url, opts) => {
    if (url === "/api/v1/risks" && (!opts || opts.method === undefined)) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([RISK]) });
    }
    if (opts?.method === "DELETE") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
  }));
});

describe("RiskRegister delete action notifies via toast (regression: ESLint flat-config no-undef)", () => {
  it("calls toast.success after a successful delete without throwing ReferenceError", async () => {
    const user = userEvent.setup();
    const toast = { success: vi.fn(), error: vi.fn() };

    render(<RiskRegister token="t" onNavigate={() => {}} toast={toast} />);

    await waitFor(() => expect(screen.getByText("Test risk")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(await screen.findByRole("button", { name: "Delete risk" }));

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("RISK-1 deleted"));
    expect(toast.error).not.toHaveBeenCalled();
  });
});
