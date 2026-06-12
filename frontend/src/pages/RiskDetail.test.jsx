/**
 * RiskDetail — STORY-002 AC-2 (test_risk_detail_prefill_remediation):
 * arriving with a suggested remediation opens the Remediation tab and
 * highlights the SARO suggestion for human validation.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import RiskDetail from "./RiskDetail";

const RISK = {
  id: "R-AB12CD",
  audit_id: null, // keep the fetch graph minimal — no trace/remediation calls
  title: "Quarterly fairness scan",
  category: "AI Quality",
  severity: "critical",
  owner: "Alex Rivera",
  dueDate: "2026-07-01",
  status: "Open",
  risk_score: 82,
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(RISK) })
  ));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RiskDetail — suggested remediation prefill (STORY-002 AC-2)", () => {
  it("opens the Remediation tab and highlights the suggestion", async () => {
    render(
      <RiskDetail
        token="tok-1"
        riskId="R-AB12CD"
        onNavigate={() => {}}
        suggestedRemediation="Re-balance the training sample."
      />
    );
    const panel = await screen.findByTestId("suggested-remediation");
    expect(panel).toHaveTextContent("Suggested by SARO");
    expect(panel).toHaveTextContent("Re-balance the training sample.");
    // STORY-004: the suggestion carries the human-validation disclaimer.
    expect(panel).toHaveTextContent("Recommended remediation — human validation required");
  });

  it("defaults to the Details tab without a suggestion", async () => {
    render(<RiskDetail token="tok-1" riskId="R-AB12CD" onNavigate={() => {}} />);
    await screen.findAllByText("Quarterly fairness scan");
    expect(screen.queryByTestId("suggested-remediation")).not.toBeInTheDocument();
    expect(screen.getByText("Category")).toBeInTheDocument();
  });
});
