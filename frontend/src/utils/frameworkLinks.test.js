/**
 * STORY-003 AC-2: deep-link target generation (test_framework_deep_link_generation).
 */
import { describe, it, expect } from "vitest";
import { getFrameworkTarget } from "./frameworkLinks";

describe("getFrameworkTarget", () => {
  it.each([
    ["NIST AI RMF", "nist-ai-rmf"],
    ["EU AI Act", "eu-ai-act"],
    ["ISO 42001", "iso-42001"],
    ["AIGP", "aigp"],
  ])("maps %s to a claims_matrix section", (framework, section) => {
    const target = getFrameworkTarget(framework);
    expect(target).toEqual({
      page: "claims_matrix",
      section,
      label: `View ${framework} reference`,
    });
  });

  it("is case/whitespace tolerant", () => {
    expect(getFrameworkTarget(" nist ai rmf ")).toMatchObject({ section: "nist-ai-rmf" });
  });

  it("returns null when no documented target exists (AC-3)", () => {
    expect(getFrameworkTarget("SOC 2")).toBeNull();
    expect(getFrameworkTarget(null)).toBeNull();
    expect(getFrameworkTarget("")).toBeNull();
  });

  it("labels use explicit action text, not generic 'Learn more' (NFR)", () => {
    const target = getFrameworkTarget("EU AI Act");
    expect(target.label).toBe("View EU AI Act reference");
    expect(target.label).not.toMatch(/learn more/i);
  });
});
