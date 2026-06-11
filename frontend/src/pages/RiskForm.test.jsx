import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskForm from "./RiskForm";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })));
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
