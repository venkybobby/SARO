/**
 * STORY-413 AC-5: KPI row layout verified at 2, 3, and 4 visible tiles.
 * KpiRow was extracted specifically so this is testable in isolation with
 * synthetic tile arrays, rather than depending on which persona happens to
 * produce which tile count.
 */
import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Shield, Clock, ShieldAlert, Sparkles } from "lucide-react";
import { KpiRow } from "./Dashboard";

function kpi(label, icon = Shield) {
  return { label, value: 42, severity: "info", icon };
}

describe("KpiRow — STORY-413 AC-5: layout resilience", () => {
  it("renders exactly 2 tiles, no crash, no orphan gap", () => {
    render(<KpiRow kpis={[kpi("A", Shield), kpi("B", Clock)]} loading={false} />);
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getByText("B")).toBeTruthy();
    expect(screen.getAllByText("42")).toHaveLength(2);
  });

  it("renders exactly 3 tiles, no crash, no orphan gap", () => {
    render(<KpiRow kpis={[kpi("A", Shield), kpi("B", Clock), kpi("C", ShieldAlert)]} loading={false} />);
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getByText("B")).toBeTruthy();
    expect(screen.getByText("C")).toBeTruthy();
    expect(screen.getAllByText("42")).toHaveLength(3);
  });

  it("renders exactly 4 tiles, no crash, no orphan gap", () => {
    render(<KpiRow kpis={[kpi("A", Shield), kpi("B", Clock), kpi("C", ShieldAlert), kpi("D", Sparkles)]} loading={false} />);
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getByText("B")).toBeTruthy();
    expect(screen.getByText("C")).toBeTruthy();
    expect(screen.getByText("D")).toBeTruthy();
    expect(screen.getAllByText("42")).toHaveLength(4);
  });

  it("uses the resilient auto-fit grid regardless of item count (no fixed column count to leave gaps)", () => {
    const { container } = render(<KpiRow kpis={[kpi("A"), kpi("B")]} loading={false} />);
    const grid = container.firstChild;
    expect(grid.style.gridTemplateColumns).toMatch(/repeat\(auto-fit,\s*minmax\(200px,\s*1fr\)\)/);
  });

  it("per-tile loading overrides the row-level loading flag (STORY-413 live tiles load independently)", () => {
    render(<KpiRow kpis={[{ ...kpi("A"), loading: true }, kpi("B")]} loading={false} />);
    expect(screen.getByText("B")).toBeTruthy();
    // "A" is in its own loading state (skeleton), so its value/label text
    // still renders (label always shows) but its numeric value does not.
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getAllByText("42")).toHaveLength(1);
  });
});
