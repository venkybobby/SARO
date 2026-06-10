import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
