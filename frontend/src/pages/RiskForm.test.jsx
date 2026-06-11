import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RiskForm from "./RiskForm";

const SOURCE_PATH = path.resolve(__dirname, "./RiskForm.jsx");

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })));
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
