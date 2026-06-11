/**
 * AI Insights API client — STORY-001 data wiring.
 *
 * Fetches real compliance-scoring insights from the SARO backend. Insights
 * missing their confidence context are dropped client-side and logged
 * (compliance NFR: never render guidance without uncertainty context).
 */
const SARO_API_URL = process.env.REACT_APP_SARO_API_URL || "";

export const FETCH_TIMEOUT_MS = 10_000;

export class InsightsApiError extends Error {
  constructor(message, { status = null, detail = null, timedOut = false } = {}) {
    super(message);
    this.name = "InsightsApiError";
    this.status = status;
    this.detail = detail;
    this.timedOut = timedOut;
  }
}

function isRenderableInsight(insight) {
  return Boolean(
    insight &&
    insight.id &&
    insight.title &&
    insight.description &&
    typeof insight.confidence === "number"
  );
}

export async function fetchInsights(token, { riskId, signal, timeoutMs = FETCH_TIMEOUT_MS } = {}) {
  const params = new URLSearchParams();
  if (riskId) params.set("risk_id", riskId);
  const qs = params.toString();
  const url = `${SARO_API_URL}/api/v1/insights${qs ? `?${qs}` : ""}`;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response;
  try {
    response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) {
      throw new InsightsApiError("Insights request timed out", { timedOut: true });
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    throw new InsightsApiError(`Insights API ${response.status}`, { status: response.status });
  }

  const body = await response.json();
  const all = Array.isArray(body.insights) ? body.insights : [];
  const insights = all.filter(isRenderableInsight);
  const dropped = all.length - insights.length;
  if (dropped > 0) {
    console.warn(
      `insightsService: dropped ${dropped} insight(s) missing required fields (confidence/title/description)`,
      all.filter((i) => !isRenderableInsight(i)).map((i) => i && i.id)
    );
  }
  return { insights, count: insights.length, dropped };
}

export async function postInsightAction(token, insightId, action, { confirmHumanReview = false } = {}) {
  const response = await fetch(`${SARO_API_URL}/api/v1/insights/${encodeURIComponent(insightId)}/action`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ action, confirm_human_review: confirmHumanReview }),
  });

  if (!response.ok) {
    let detail = null;
    try {
      detail = (await response.json()).detail || null;
    } catch {
      /* non-JSON error body */
    }
    throw new InsightsApiError(`Insight action API ${response.status}`, {
      status: response.status,
      detail,
    });
  }
  return response.json();
}
