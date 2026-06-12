/**
 * FND-007 pinning test: `risk_detail` navigation silently fell through to
 * Dashboard because the page key was never registered in PAGE_COMPONENTS,
 * and RiskDetail's riskId prop was never wired from the nav payload.
 * RiskRegister's View button and AI Insights' Apply flow both depend on it.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import path from "path";

const SOURCE = readFileSync(path.resolve(__dirname, "./App.jsx"), "utf-8");

describe("FND-007 — risk_detail page registration", () => {
  it("registers risk_detail in PAGE_COMPONENTS", () => {
    expect(SOURCE).toMatch(/risk_detail:\s*RiskDetail/);
  });

  it("wires riskId from the navigation payload", () => {
    expect(SOURCE).toMatch(/riskId=\{/);
    expect(SOURCE).toMatch(/suggestedRemediation=\{/);
  });

  it("navigation sources still target the risk_detail page key", () => {
    const riskRegister = readFileSync(
      path.resolve(__dirname, "./pages/RiskRegister.jsx"), "utf-8"
    );
    expect(riskRegister).toMatch(/onNavigate\?\.\("risk_detail"/);
  });
});
