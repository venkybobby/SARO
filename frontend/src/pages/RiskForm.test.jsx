import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskForm from "./RiskForm";

const SOURCE_PATH = path.resolve(__dirname, "./RiskForm.jsx");

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

describe("RiskForm — design tokens (STORY-RISKFORM-002)", () => {
  it("AC-1: contains no hardcoded hex color literals", () => {
    const source = readFileSync(SOURCE_PATH, "utf-8");
    expect(source).not.toMatch(/#fca5a5/i);
    expect(source).not.toMatch(/#d1d5db/i);
    expect(source).not.toMatch(/#ef4444/i);
    expect(source).not.toMatch(/#[0-9a-f]{3,6}/i);
  });

  it("AC-2: error state uses var(--color-critical) for border and error text", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const submit = screen.getByRole("button", { name: /Create Risk/i });
    await user.click(submit);

    const title = screen.getByPlaceholderText("Describe the risk…");
    expect(title.style.border).toContain("var(--color-critical)");

    const error = await screen.findByText("Title is required");
    expect(error.style.color).toBe("var(--color-critical)");
  });

  it("AC-3: default (non-error) input border uses var(--color-border-default)", () => {
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    expect(title.style.border).toContain("var(--color-border-default)");
  });

  it("required field asterisks use var(--color-critical)", () => {
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const asterisks = screen.getAllByText("*");
    expect(asterisks.length).toBeGreaterThan(0);
    for (const a of asterisks) {
      expect(a.style.color).toBe("var(--color-critical)");
    }
  });
});

describe("RiskForm — onBlur field validation (STORY-RISKFORM-001)", () => {
  it("AC-1: shows an inline error when a required field is left empty on blur", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    await user.click(title);
    await user.tab();

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
  });

  it("AC-2: clears the error immediately when the field is corrected (onChange)", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    await user.click(title);
    await user.tab();
    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    await user.type(title, "New AI risk");
    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
  });

  it("AC-3: submit still validates all required fields at once", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const submit = screen.getByRole("button", { name: /Create Risk/i });
    await user.click(submit);

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(screen.getByText("Owner is required")).toBeInTheDocument();
    expect(screen.getByText("Due date is required")).toBeInTheDocument();
  });

  it("AC-4: correcting one error leaves remaining errors and does not submit", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<RiskForm token="t" onNavigate={onNavigate} toast={{}} />);

    const submit = screen.getByRole("button", { name: /Create Risk/i });
    await user.click(submit);
    expect(await screen.findByText("Title is required")).toBeInTheDocument();

    const title = screen.getByPlaceholderText("Describe the risk…");
    await user.type(title, "New AI risk");

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
    expect(screen.getByText("Owner is required")).toBeInTheDocument();
    expect(screen.getByText("Due date is required")).toBeInTheDocument();
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("edge case: rapid tab-through triggers errors for each empty required field in sequence", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    const owner = screen.getByPlaceholderText("Name or email…");

    await user.click(title);
    await user.tab();
    await user.tab(); // through description
    await user.tab(); // through category
    await user.tab(); // through severity

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(owner).toHaveFocus();

    await user.tab();
    expect(await screen.findByText("Owner is required")).toBeInTheDocument();
  });

  it("edge case: clearing a corrected field back to empty keeps it in error state", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    await user.type(title, "Temp");
    await user.clear(title);
    await user.tab();

    expect(await screen.findByText("Title is required")).toBeInTheDocument();
  });

  it("edge case: pre-filled edit mode does not show errors on initial render", async () => {
    global.fetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve([
          { audit_id: "r1", title: "", owner: "", dueDate: "", category: "AI Quality", severity: "medium", status: "Open", description: "" },
        ]),
      })
    );

    render(<RiskForm token="t" riskId="r1" onNavigate={() => {}} toast={{}} />);

    await waitFor(() => expect(screen.getByPlaceholderText("Describe the risk…")).toBeInTheDocument());

    expect(screen.queryByText("Title is required")).not.toBeInTheDocument();
    expect(screen.queryByText("Owner is required")).not.toBeInTheDocument();
    expect(screen.queryByText("Due date is required")).not.toBeInTheDocument();
  });

  it("AC-1/NFR: error messages are associated with their field via aria-describedby", async () => {
    const user = userEvent.setup();
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const title = screen.getByPlaceholderText("Describe the risk…");
    await user.click(title);
    await user.tab();

    const error = await screen.findByText("Title is required");
    expect(error).toHaveAttribute("id");
    expect(title).toHaveAttribute("aria-describedby", error.id);
  });
});

function getActionRow() {
  const disclaimer = screen.getByText(/Human review required before any action is taken on this risk\./i);
  return { disclaimer, row: disclaimer.parentElement };
}

describe("RiskForm action row layout (STORY-RISKFORM-004)", () => {
  it("AC-1/AC-3/AC-4: action row uses flex-wrap so it reflows on narrow/constrained widths", () => {
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const { row } = getActionRow();
    expect(row.style.display).toBe("flex");
    expect(row.style.flexWrap).toBe("wrap");
    expect(row.style.gap).toBeTruthy();
  });

  it("AC-2: Save and Cancel buttons sit in the same row container as the disclaimer", () => {
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const { row, disclaimer } = getActionRow();
    const saveButton = screen.getByRole("button", { name: /Create Risk/i });
    const cancelButton = screen.getByRole("button", { name: /Cancel/i });

    expect(row.contains(saveButton)).toBe(true);
    expect(row.contains(cancelButton)).toBe(true);
    expect(row.contains(disclaimer)).toBe(true);
  });

  it("disclaimer text is allowed to wrap onto multiple lines (no forced single line)", () => {
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const { disclaimer } = getActionRow();
    expect(disclaimer.style.whiteSpace).not.toBe("nowrap");
  });

  it("edge case: a disabled Save button does not break the action row layout", () => {
    render(<RiskForm token="t" onNavigate={() => {}} toast={{}} />);

    const { row } = getActionRow();
    const saveButton = screen.getByRole("button", { name: /Create Risk/i });

    expect(row.style.flexWrap).toBe("wrap");
    expect(row.contains(saveButton)).toBe(true);
  });
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
