/**
 * STORY-TAB-003 / FND-076 — Coverage Gap binds the real coverage API fields.
 *
 * Contract pinned (routers/compliance_matrix.py GET /coverage):
 *   {frameworks:[{framework, total_rules, covered, partial, not_covered,
 *                 coverage_pct, last_updated}],
 *    overall_coverage_pct, framework_count, total_rules}
 *
 * Pre-fix the page read fw.name / fw.gaps / fw.controls_* (none exist) →
 * blank framework names and "No gaps identified for undefined".
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CoverageGap from "./CoverageGap";

const COVERAGE = {
  frameworks: [
    { framework: "EU AI Act",   total_rules: 8, covered: 5, partial: 2, not_covered: 1, coverage_pct: 75.0, last_updated: "2026-06-01" },
    { framework: "ISO 42001",   total_rules: 3, covered: 0, partial: 0, not_covered: 3, coverage_pct: 0.0,  last_updated: null },
    { framework: "AIGP Framework", total_rules: 2, covered: 2, partial: 0, not_covered: 0, coverage_pct: 100.0, last_updated: "2026-01-20" },
  ],
  overall_coverage_pct: 61.5,
  framework_count: 3,
  total_rules: 13,
};

function ok(json) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(json) });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-003 AC-1 / FND-076: framework list binds real fields", () => {
  it("renders each framework's name and coverage_pct — including a 0% one", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(COVERAGE)));
    render(<CoverageGap token="t" tenantId="tid" />);

    expect(await screen.findByText("EU AI Act")).toBeInTheDocument();
    expect(screen.getByText("ISO 42001")).toBeInTheDocument();
    expect(screen.getByText("AIGP Framework")).toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/undefined/);
  });
});

describe("STORY-TAB-003 AC-2/AC-3: detail pane shows the real breakdown", () => {
  it("selected framework shows covered/partial/not-covered against total_rules and last_updated", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(() => ok(COVERAGE)));
    render(<CoverageGap token="t" tenantId="tid" />);

    await user.click(await screen.findByText("EU AI Act"));
    expect(await screen.findByText(/1 of 8 rules not covered/)).toBeInTheDocument();
    expect(screen.getByText(/Covered: 5/)).toBeInTheDocument();
    expect(screen.getByText(/Partial: 2/)).toBeInTheDocument();
    expect(screen.getByText(/Last updated: 2026-06-01/)).toBeInTheDocument();
    // the phantom-field artifacts must be gone
    expect(screen.queryByText(/No gaps identified for undefined/)).not.toBeInTheDocument();
    expect(screen.queryByText(/controls covered/)).not.toBeInTheDocument();
  });

  it("fully covered framework (not_covered=0, partial=0) shows a positive state naming it", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(() => ok(COVERAGE)));
    render(<CoverageGap token="t" tenantId="tid" />);
    await user.click(await screen.findByText("AIGP Framework"));
    expect(await screen.findByText(/All 2 rules covered for AIGP Framework/)).toBeInTheDocument();
  });

  it("edge: last_updated null renders no 'Last updated' row and no 'null' text", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(() => ok(COVERAGE)));
    render(<CoverageGap token="t" tenantId="tid" />);
    await user.click(await screen.findByText("ISO 42001"));
    expect(await screen.findByText(/3 of 3 rules not covered/)).toBeInTheDocument();
    expect(screen.queryByText(/Last updated:/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/null/);
  });
});

describe("STORY-TAB-003 AC-4: overall summary from the API rollup", () => {
  it("renders overall coverage across frameworks and rules", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(COVERAGE)));
    render(<CoverageGap token="t" tenantId="tid" />);
    expect(await screen.findByText(/Overall coverage: 61\.5%/)).toBeInTheDocument();
    expect(screen.getByText(/3 frameworks · 13 rules/)).toBeInTheDocument();
  });
});

describe("STORY-TAB-003 AC-5: error and empty states", () => {
  it("non-2xx renders the error banner", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    render(<CoverageGap token="t" tenantId="tid" />);
    expect(await screen.findByText(/⚠/)).toBeInTheDocument();
  });

  it("empty frameworks array renders an explicit no-data state, not a blank page", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({ frameworks: [], overall_coverage_pct: 0.0, framework_count: 0, total_rules: 0 })));
    render(<CoverageGap token="t" tenantId="tid" />);
    expect(await screen.findByText(/No coverage data/i)).toBeInTheDocument();
  });
});
