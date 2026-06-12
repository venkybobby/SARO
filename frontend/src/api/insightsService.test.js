/**
 * insightsService — STORY-001 (data wiring) + STORY-005 (honest fetch lifecycle).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchInsights, postInsightAction, InsightsApiError } from "./insightsService";

const VALID_INSIGHT = {
  id: "INS-AB12CD34",
  risk_id: "R-AB12CD",
  title: "Fairness Gate flagged in Quarterly scan",
  description: "Parity gap exceeds threshold. SARO scored this output at 82/100.",
  confidence: 0.87,
  severity: "critical",
  framework: "NIST AI RMF",
  remediation_guidance: "Re-balance the training sample.",
  status: "active",
  human_review_required: true,
  _traceability: { engine_version: "8.0.0", assessment_date: "2026-06-01", audit_id: "x" },
};

function okResponse(body) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => okResponse({ insights: [VALID_INSIGHT], count: 1 })));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("fetchInsights (STORY-001 AC-1)", () => {
  it("calls /api/v1/insights with bearer token", async () => {
    await fetchInsights("tok-1");
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain("/api/v1/insights");
    expect(opts.headers.Authorization).toBe("Bearer tok-1");
  });

  it("carries the risk context as a query param", async () => {
    await fetchInsights("tok-1", { riskId: "R-AB12CD" });
    const [url] = fetch.mock.calls[0];
    expect(url).toContain("risk_id=R-AB12CD");
  });

  it("returns the parsed insights", async () => {
    const result = await fetchInsights("tok-1");
    expect(result.insights).toHaveLength(1);
    expect(result.insights[0].id).toBe("INS-AB12CD34");
  });

  it("throws InsightsApiError on a non-OK response (STORY-001 AC-3)", async () => {
    fetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 502, json: () => Promise.resolve({}) })
    );
    await expect(fetchInsights("tok-1")).rejects.toBeInstanceOf(InsightsApiError);
    await expect(fetchInsights("tok-1")).rejects.toMatchObject({ status: 502 });
  });

  it("aborts after the timeout and flags timedOut (STORY-005 edge: 10s timeout)", async () => {
    vi.useFakeTimers();
    fetch.mockImplementation((_url, { signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () =>
          reject(Object.assign(new Error("aborted"), { name: "AbortError" }))
        );
      })
    );
    const pending = fetchInsights("tok-1");
    const assertion = expect(pending).rejects.toMatchObject({ timedOut: true });
    await vi.advanceTimersByTimeAsync(10_000);
    await assertion;
  });

  it("drops insights missing confidence context and logs the validation failure (NFR)", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const invalid = { ...VALID_INSIGHT, id: "INS-BAD00000", confidence: null };
    fetch.mockImplementation(() => okResponse({ insights: [VALID_INSIGHT, invalid], count: 2 }));

    const result = await fetchInsights("tok-1");
    expect(result.insights).toHaveLength(1);
    expect(result.insights[0].id).toBe("INS-AB12CD34");
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("postInsightAction (STORY-002 AC-3)", () => {
  it("POSTs the action with human-review acknowledgement", async () => {
    fetch.mockImplementation(() =>
      okResponse({ id: "INS-AB12CD34", risk_id: "R-AB12CD", status: "accepted" })
    );
    const result = await postInsightAction("tok-1", "INS-AB12CD34", "accepted", {
      confirmHumanReview: true,
    });
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain("/api/v1/insights/INS-AB12CD34/action");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ action: "accepted", confirm_human_review: true });
    expect(result.status).toBe("accepted");
  });

  it("throws with status on access denied (STORY-002 edge: permission)", async () => {
    fetch.mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ detail: "Read-only persona" }),
      })
    );
    await expect(
      postInsightAction("tok-1", "INS-AB12CD34", "dismissed")
    ).rejects.toMatchObject({ status: 403, detail: "Read-only persona" });
  });
});
