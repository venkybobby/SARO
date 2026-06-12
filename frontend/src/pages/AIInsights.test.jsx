/**
 * AI Insights page — SARO_AIInsights_Stories STORY-001…006.
 *
 * The insights service module is mocked so each test controls the fetch
 * lifecycle explicitly (STORY-005: loading must mirror the real promise).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import path from "path";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AIInsights, { DISCLAIMER_TEXT, NO_REMEDIATION_TEXT } from "./AIInsights";
import { fetchInsights, postInsightAction } from "../api/insightsService";

vi.mock("../api/insightsService", () => ({
  fetchInsights: vi.fn(),
  postInsightAction: vi.fn(),
}));

const SOURCE_PATH = path.resolve(__dirname, "./AIInsights.jsx");

const INSIGHT_NIST = {
  id: "INS-AB12CD34",
  risk_id: "R-AB12CD",
  title: "Fairness Gate flagged in Quarterly scan",
  description: "Parity gap exceeds threshold. SARO scored this output at 82/100.",
  confidence: 0.87,
  basis: "2 flagged check(s) across scan 'Quarterly scan'",
  severity: "critical",
  framework: "NIST AI RMF",
  framework_section: "MEASURE 2.11",
  remediation_guidance: "Re-balance the training sample.",
  status: "active",
  human_review_required: true,
  _traceability: { engine_version: "8.0.0", assessment_date: "2026-06-01", audit_id: "a1" },
};

const INSIGHT_NO_REMEDIATION = {
  ...INSIGHT_NIST,
  id: "INS-EE55FF66",
  risk_id: "R-EE55FF",
  title: "Drift pattern in scoring model",
  description: "KS-test p-value below 0.05 for 3 days. SARO scored this output at 58/100.",
  framework: null,
  framework_section: null,
  remediation_guidance: null,
  confidence: 0.72,
  severity: "high",
};

const INSIGHT_HIGH_CONFIDENCE = {
  ...INSIGHT_NIST,
  id: "INS-99887766",
  risk_id: "R-998877",
  title: "Consent gap in onboarding flow",
  description: "Granular consent categories are not recorded. SARO scored this output at 64/100.",
  confidence: 0.96,
  severity: "medium",
  framework: "EU AI Act",
  framework_section: "Art. 13",
  remediation_guidance: "Record granular consent categories at onboarding.",
};

const ALL_INSIGHTS = [INSIGHT_NIST, INSIGHT_NO_REMEDIATION, INSIGHT_HIGH_CONFIDENCE];

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function renderPage(props = {}) {
  const toast = { success: vi.fn(), error: vi.fn() };
  const onNavigate = vi.fn();
  const utils = render(
    <AIInsights
      token="tok-1"
      user={{ email: "venky@saro.test", persona_role: "compliance_lead" }}
      toast={toast}
      onNavigate={onNavigate}
      {...props}
    />
  );
  return { ...utils, toast, onNavigate };
}

beforeEach(() => {
  fetchInsights.mockResolvedValue({ insights: ALL_INSIGHTS, count: 3 });
  postInsightAction.mockImplementation((_t, id, action) =>
    Promise.resolve({ id, status: action })
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// ── STORY-001: data wiring ──────────────────────────────────────────────────

describe("STORY-001 — backend data wiring", () => {
  it("AC-1: fetches insights on mount with the current risk context (test_insights_api_fetch_on_mount)", async () => {
    renderPage({ initialRiskId: "R-AB12CD" });
    await waitFor(() => expect(fetchInsights).toHaveBeenCalledTimes(1));
    expect(fetchInsights).toHaveBeenCalledWith(
      "tok-1",
      expect.objectContaining({ riskId: "R-AB12CD" })
    );
  });

  it("AC-2: renders real API fields on the card (test_insights_render_api_data)", async () => {
    renderPage();
    expect(await screen.findByText(INSIGHT_NIST.title)).toBeInTheDocument();
    expect(screen.getByText(INSIGHT_NIST.description)).toBeInTheDocument();
    expect(screen.getByText(/High confidence · 87%/)).toBeInTheDocument();
    expect(screen.getByText(INSIGHT_NIST.remediation_guidance)).toBeInTheDocument();
    expect(screen.getByText("View NIST AI RMF reference")).toBeInTheDocument();
  });

  it("AC-2: no hardcoded mock data remains in the source", () => {
    const source = readFileSync(SOURCE_PATH, "utf-8");
    expect(source).not.toMatch(/MOCK_INSIGHTS/);
    expect(source).not.toMatch(/Uncontrolled risk approaching escalation window/);
  });

  it("AC-3: API error shows an error state with retry — never mock data (test_insights_error_state)", async () => {
    const user = userEvent.setup();
    fetchInsights.mockRejectedValueOnce(
      Object.assign(new Error("Insights API 502"), { status: 502 })
    );
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not load insights/i);
    expect(screen.queryByText(/uncontrolled risk/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(fetchInsights).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(INSIGHT_NIST.title)).toBeInTheDocument();
  });

  it("AC-3: timeout shows a timeout message (test_insights_timeout)", async () => {
    fetchInsights.mockRejectedValueOnce(
      Object.assign(new Error("Insights request timed out"), { timedOut: true })
    );
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent(/timed out/i);
  });

  it("AC-4: a fresh fetch happens on every mount (test_insights_data_refresh_on_unmount)", async () => {
    const { unmount } = renderPage();
    await waitFor(() => expect(fetchInsights).toHaveBeenCalledTimes(1));
    unmount();
    renderPage();
    await waitFor(() => expect(fetchInsights).toHaveBeenCalledTimes(2));
  });

  it("edge: empty array shows the empty state, not mock data", async () => {
    fetchInsights.mockResolvedValueOnce({ insights: [], count: 0 });
    renderPage();
    expect(await screen.findByText("No active insights")).toBeInTheDocument();
    expect(screen.queryByText(/uncontrolled risk/i)).not.toBeInTheDocument();
  });
});

// ── STORY-005: honest loading state ─────────────────────────────────────────

describe("STORY-005 — loading state tied to the real fetch", () => {
  it("AC-1: loading shows immediately when the fetch starts (test_loading_state_starts_with_fetch)", () => {
    const d = deferred();
    fetchInsights.mockReturnValueOnce(d.promise);
    renderPage();
    expect(screen.getByRole("status")).toHaveTextContent(/fetching insights/i);
    d.resolve({ insights: [], count: 0 });
  });

  it("AC-2/AC-4: loading clears the moment data arrives — no fixed delay (test_loading_state_ends_on_data_arrival)", async () => {
    const d = deferred();
    fetchInsights.mockReturnValueOnce(d.promise);
    renderPage();
    expect(screen.getByRole("status")).toBeInTheDocument();

    d.resolve({ insights: ALL_INSIGHTS, count: 3 });
    expect(await screen.findByText(INSIGHT_NIST.title)).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("AC-3: loading persists exactly while the request is in flight (test_loading_duration_matches_network_time)", async () => {
    const d = deferred();
    fetchInsights.mockReturnValueOnce(d.promise);
    renderPage();

    // Still loading until the promise settles — there is no timer that hides it.
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByRole("status")).toBeInTheDocument();

    d.resolve({ insights: [], count: 0 });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("AC-5: loading clears on fetch error (test_loading_cleared_on_fetch_error)", async () => {
    fetchInsights.mockRejectedValueOnce(new Error("boom"));
    renderPage();
    await screen.findByRole("alert");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("NFR: no artificial setTimeout delay remains and the label is honest", () => {
    const source = readFileSync(SOURCE_PATH, "utf-8");
    expect(source).not.toMatch(/setTimeout\([^)]*2200/);
    expect(source).not.toMatch(/2200/);
    expect(source).toMatch(/Fetching insights/);
    expect(source).not.toMatch(/Analyzing your risk register/);
  });
});

// ── STORY-004: human review framing ─────────────────────────────────────────

describe("STORY-004 — human validation framing", () => {
  it("AC-1: the exact ClaimsMatrix disclaimer appears on every card with remediation (test_disclaimer_visible_on_insight_card)", async () => {
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const disclaimers = screen.getAllByText(DISCLAIMER_TEXT);
    // NIST + high-confidence cards carry remediation; the third reframes.
    expect(disclaimers.length).toBe(2);
  });

  it("AC-2: the explainer is available on interaction (test_disclaimer_tooltip_on_hover)", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const infoButtons = screen.getAllByRole("button", { name: /why is human review required/i });
    await user.click(infoButtons[0]);
    expect(
      screen.getByText(/require compliance review before deployment/i)
    ).toBeInTheDocument();
  });

  it("AC-3: applying opens a confirmation restating the requirement (test_apply_confirmation_shows_disclaimer)", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    await user.click(screen.getAllByRole("button", { name: /apply suggestion/i })[0]);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(DISCLAIMER_TEXT);
  });

  it("AC-4: disclaimer is equally present at >90% confidence (test_disclaimer_visible_at_high_confidence)", async () => {
    fetchInsights.mockResolvedValueOnce({ insights: [INSIGHT_HIGH_CONFIDENCE], count: 1 });
    renderPage();
    await screen.findByText(INSIGHT_HIGH_CONFIDENCE.title);
    const disclaimer = screen.getByTestId("human-review-disclaimer");
    expect(disclaimer).toHaveTextContent(DISCLAIMER_TEXT);
  });

  it("edge: insights without remediation reframe the disclaimer", async () => {
    fetchInsights.mockResolvedValueOnce({ insights: [INSIGHT_NO_REMEDIATION], count: 1 });
    renderPage();
    await screen.findByText(INSIGHT_NO_REMEDIATION.title);
    expect(screen.getByText(NO_REMEDIATION_TEXT)).toBeInTheDocument();
  });

  it("edge: read-only auditor persona sees the disclaimer but cannot act", async () => {
    renderPage({ user: { email: "a@saro.test", persona_role: "ai_auditor" } });
    await screen.findByText(INSIGHT_NIST.title);
    expect(screen.getAllByText(DISCLAIMER_TEXT).length).toBeGreaterThan(0);
    for (const btn of screen.getAllByRole("button", { name: /apply suggestion/i })) {
      expect(btn).toBeDisabled();
    }
  });
});

// ── STORY-002: apply suggestion ─────────────────────────────────────────────

describe("STORY-002 — apply suggestion action", () => {
  async function applyFirstSuggestion(user) {
    await screen.findByText(INSIGHT_NIST.title);
    await user.click(screen.getAllByRole("button", { name: /apply suggestion/i })[0]);
    await user.click(await screen.findByRole("button", { name: /apply — i will validate/i }));
  }

  it("AC-1: confirming navigates to risk detail with the suggested remediation (test_apply_suggestion_navigation)", async () => {
    const user = userEvent.setup();
    const { onNavigate } = renderPage();
    await applyFirstSuggestion(user);
    await waitFor(() =>
      expect(onNavigate).toHaveBeenCalledWith("risk_detail", {
        riskId: INSIGHT_NIST.risk_id,
        suggestedRemediation: INSIGHT_NIST.remediation_guidance,
        insightId: INSIGHT_NIST.id,
      })
    );
  });

  it("AC-3: the action posts with human-review acknowledgement (test_audit_event_apply_suggestion)", async () => {
    const user = userEvent.setup();
    renderPage();
    await applyFirstSuggestion(user);
    await waitFor(() =>
      expect(postInsightAction).toHaveBeenCalledWith(
        "tok-1",
        INSIGHT_NIST.id,
        "accepted",
        { confirmHumanReview: true }
      )
    );
  });

  it("AC-4: status flips to accepted and a confirmation message shows (test_insight_status_update_after_apply)", async () => {
    const user = userEvent.setup();
    const { toast } = renderPage();
    await applyFirstSuggestion(user);
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith(expect.stringContaining(`Remediation applied to ${INSIGHT_NIST.risk_id}`))
    );
    // Card leaves the active tab; accepted tab count reflects it.
    expect(screen.queryByText(INSIGHT_NIST.title)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accepted \(1\)/i })).toBeInTheDocument();
  });

  it("edge: deleted risk (404) shows a specific error and removes the card", async () => {
    const user = userEvent.setup();
    postInsightAction.mockRejectedValueOnce(Object.assign(new Error("404"), { status: 404 }));
    const { toast, onNavigate } = renderPage();
    await applyFirstSuggestion(user);
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("no longer exists"))
    );
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("edge: permission denied (403) shows access denied, not a generic error", async () => {
    const user = userEvent.setup();
    postInsightAction.mockRejectedValueOnce(
      Object.assign(new Error("403"), { status: 403, detail: null })
    );
    const { toast, onNavigate } = renderPage();
    await applyFirstSuggestion(user);
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/access denied/i))
    );
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("NFR: the apply button is labeled with the remediation context", async () => {
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    expect(
      screen.getByRole("button", { name: `Apply suggestion: ${INSIGHT_NIST.remediation_guidance}` })
    ).toBeInTheDocument();
  });
});

// ── STORY-003: framework reference links ────────────────────────────────────

describe("STORY-003 — framework reference links", () => {
  it("AC-1/AC-2: clicking the link navigates to the claims matrix section (test_framework_reference_navigation)", async () => {
    const user = userEvent.setup();
    const { onNavigate } = renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    await user.click(screen.getByText("View NIST AI RMF reference"));
    expect(onNavigate).toHaveBeenCalledWith("claims_matrix", { section: "nist-ai-rmf" });
  });

  it("AC-3: no framework → no reference link rendered (test_framework_reference_hidden_when_no_target)", async () => {
    fetchInsights.mockResolvedValueOnce({ insights: [INSIGHT_NO_REMEDIATION], count: 1 });
    renderPage();
    await screen.findByText(INSIGHT_NO_REMEDIATION.title);
    expect(screen.queryByText(/view .* reference/i)).not.toBeInTheDocument();
  });

  it("NFR: scroll position restores after returning from a framework reference (AC-4)", async () => {
    const main = document.createElement("div");
    main.id = "main-content";
    document.body.appendChild(main);
    try {
      const user = userEvent.setup();
      const first = renderPage();
      await screen.findByText(INSIGHT_NIST.title);
      main.scrollTop = 420;
      await user.click(screen.getByText("View NIST AI RMF reference"));
      first.unmount(); // navigation away unmounts the page

      main.scrollTop = 0;
      renderPage(); // returning re-mounts and refetches
      await screen.findByText(INSIGHT_NIST.title);
      await waitFor(() => expect(main.scrollTop).toBe(420));
    } finally {
      main.remove();
    }
  });

  it("AC-3: unmapped framework → disabled link with explanatory tooltip", async () => {
    fetchInsights.mockResolvedValueOnce({
      insights: [{ ...INSIGHT_NIST, framework: "SOC 2" }],
      count: 1,
    });
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const disabled = screen.getByText(/framework reference unavailable/i);
    expect(disabled).toHaveAttribute("aria-disabled", "true");
    expect(disabled).toHaveAttribute("title", expect.stringMatching(/no framework reference/i));
  });
});

// ── STORY-006: filter tab discoverability ───────────────────────────────────

describe("STORY-006 — filter tab discoverability", () => {
  it("AC-1: zero-count tabs are de-emphasized (test_empty_tabs_styled_with_reduced_opacity)", async () => {
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const snoozed = screen.getByRole("button", { name: /snoozed \(0\)/i });
    expect(snoozed.style.opacity).toBe("0.55");
    // Accessibility NFR: never opacity alone — aria-label carries the state.
    expect(snoozed).toHaveAttribute("aria-label", expect.stringMatching(/no items in this category/i));
  });

  it("AC-2: the populated active tab stands out (test_active_tab_emphasized_visually)", async () => {
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const active = screen.getByRole("button", { name: /^active \(3\)$/i });
    expect(active.style.opacity).toBe("1");
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("AC-3: empty tabs carry the tooltip (test_empty_tab_tooltip_on_hover)", async () => {
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const dismissed = screen.getByRole("button", { name: /dismissed \(0\)/i });
    expect(dismissed).toHaveAttribute("title", "No items in this category");
  });

  it("AC-4: styling updates when an insight changes state (test_tab_styling_updates_when_insights_change)", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const dismissButtons = screen.getAllByRole("button", { name: /^dismiss$/i });
    await user.click(dismissButtons[0]);
    await waitFor(() => {
      const dismissed = screen.getByRole("button", { name: /dismissed \(1\)/i });
      expect(dismissed.style.opacity).toBe("1");
      expect(dismissed).not.toHaveAttribute("title");
    });
  });

  it("edge: when everything is empty, tabs render normally with an empty-state message", async () => {
    fetchInsights.mockResolvedValueOnce({ insights: [], count: 0 });
    renderPage();
    await screen.findByText("No active insights");
    for (const key of ["active", "accepted", "snoozed", "dismissed"]) {
      const tab = screen.getByRole("button", { name: new RegExp(`^${key} \\(0\\)$`, "i") });
      expect(tab.style.opacity).toBe("1");
      expect(tab).not.toHaveAttribute("title");
    }
  });

  it("NFR: touch targets keep a 44px minimum height even when de-emphasized", async () => {
    renderPage();
    await screen.findByText(INSIGHT_NIST.title);
    const snoozed = screen.getByRole("button", { name: /snoozed \(0\)/i });
    expect(snoozed.style.minHeight).toBe("44px");
  });
});
