import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskForm from "./RiskForm";

const EXISTING_RISK = {
  audit_id: "risk-1",
  title: "Existing risk",
  category: "AI Quality",
  severity: "medium",
  owner: "Alice",
  dueDate: "2026-12-01",
  status: "Open",
  description: "Pre-filled description",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([EXISTING_RISK]) })));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RiskForm — unsaved changes guard (STORY-RISKFORM-003)", () => {
  it("AC-1: dirty form + Cancel shows 'Discard unsaved changes?' confirmation", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");
    await user.click(screen.getByRole("button", { name: /Cancel/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Discard unsaved changes\?/i)).toBeInTheDocument();
  });

  it("AC-3: confirming 'Discard changes' navigates away without saving", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<RiskForm token="t" onNavigate={onNavigate} toast={{}} />);

    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");
    await user.click(screen.getByRole("button", { name: /Cancel/i }));
    await user.click(await screen.findByRole("button", { name: /Discard changes/i }));

    expect(onNavigate).toHaveBeenCalledWith("risk_register");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("AC-4: choosing 'Keep editing' stays on the form with edits intact", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<RiskForm token="t" onNavigate={onNavigate} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    await user.type(title, "New risk title");
    await user.click(screen.getByRole("button", { name: /Cancel/i }));
    await user.click(await screen.findByRole("button", { name: /Keep editing/i }));

    expect(onNavigate).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(title).toHaveValue("New risk title");
  });

  it("AC-5: after a successful save, the dirty flag resets so Cancel no longer prompts", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    fetch.mockImplementation((url) => {
      if (url === "/api/v1/risks") return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    render(<RiskForm token="t" onNavigate={onNavigate} toast={{ success: vi.fn(), error: vi.fn() }} />);

    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");
    await user.type(screen.getByPlaceholderText("Name or email…"), "Bob");
    await user.type(document.querySelector('input[type="date"]'), "2026-12-31");
    await user.click(screen.getByRole("button", { name: /Create Risk/i }));

    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("risk_register"));
    onNavigate.mockClear();

    // Save resolved and reset the dirty flag; a subsequent Cancel should
    // navigate directly without prompting.
    await user.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(onNavigate).toHaveBeenCalledWith("risk_register");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("edge case: pre-filled edit mode with no changes + Cancel does NOT prompt", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<RiskForm token="t" riskId="risk-1" onNavigate={onNavigate} toast={{}} />);

    await waitFor(() => expect(screen.getByDisplayValue("Existing risk")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /Cancel/i }));

    expect(onNavigate).toHaveBeenCalledWith("risk_register");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("edge case: typing then reverting a value still counts as dirty", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<RiskForm token="t" riskId="risk-1" onNavigate={onNavigate} toast={{}} />);

    const title = await screen.findByDisplayValue("Existing risk");
    await user.type(title, "X");
    await user.keyboard("{Backspace}");
    expect(title).toHaveValue("Existing risk");

    await user.click(screen.getByRole("button", { name: /Cancel/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("registers a beforeunload guard while the form is dirty", async () => {
    const user = userEvent.setup();
    const addSpy = vi.spyOn(window, "addEventListener");

    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);
    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");

    expect(addSpy).toHaveBeenCalledWith("beforeunload", expect.any(Function));

    const handler = addSpy.mock.calls.filter((c) => c[0] === "beforeunload").at(-1)[1];
    const event = new Event("beforeunload", { cancelable: true });
    Object.defineProperty(event, "returnValue", { writable: true, value: "" });
    handler(event);
    expect(event.defaultPrevented).toBe(true);

    addSpy.mockRestore();
  });

  it("breadcrumb / Back navigation is also guarded when the form is dirty", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");
    await user.click(screen.getByRole("button", { name: /Back/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("AC-2: registers a dirty guard so App-level (sidebar) navigation can be intercepted", async () => {
    const user = userEvent.setup();
    const onRegisterDirtyGuard = vi.fn();
    render(<RiskForm token="t" onNavigate={() => {}} onRegisterDirtyGuard={onRegisterDirtyGuard} toast={{}} />);

    // Clean form: the registered guard reports not-dirty.
    let guard = onRegisterDirtyGuard.mock.calls.at(-1)[0];
    expect(guard()).toBe(false);

    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");

    // Dirty form: App's sidebar handler would now block navigation.
    guard = onRegisterDirtyGuard.mock.calls.at(-1)[0];
    expect(guard()).toBe(true);
  });

  it("session expiry / unmount: cleans up listeners and the dirty guard without throwing", async () => {
    const user = userEvent.setup();
    const onRegisterDirtyGuard = vi.fn();
    const { unmount } = render(
      <RiskForm token="t" onNavigate={() => {}} onRegisterDirtyGuard={onRegisterDirtyGuard} toast={{}} />
    );

    await user.type(screen.getByPlaceholderText("Describe the risk…"), "New risk title");

    // Simulate the host app removing RiskForm (e.g. session expiry redirect)
    // — this must not show a confirmation dialog or throw.
    expect(() => unmount()).not.toThrow();
    expect(onRegisterDirtyGuard).toHaveBeenLastCalledWith(null);
  });
});
