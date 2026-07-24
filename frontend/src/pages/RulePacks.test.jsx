/**
 * STORY-TAB-006 / FND-081 — Rule Packs: list shows rule_count; selecting a
 * pack fetches its detail (with rules) from /api/v1/rules/packs/{framework}.
 *
 * Pre-fix the page rendered pack.rules?.length || 0 from the LIST response
 * (which carries rule_count but never rules) → every pack showed "0 rules"
 * and the detail pane never listed a single rule.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RulePacks from "./RulePacks";

const LIST = {
  packs: [
    {
      name: "EU AI Act", version: "1.0.0", framework: "EU-AI-ACT-2024",
      last_updated: "2026-02-01", status: "active", rule_count: 3,
      changelog: [{ version: "1.0.0", date: "2026-02-01", changes: ["Initial release covering Annex III high-risk categories"] }],
      file: "eu_ai_act_v1.0.yaml",
    },
    {
      name: "NIST AI Risk Management Framework", version: "1.0.0", framework: "NIST-AI-RMF",
      last_updated: "2026-01-15", status: "active", rule_count: 6,
      changelog: [], file: "nist_rmf_v1.0.yaml",
    },
  ],
  total: 2,
};

const EU_DETAIL = {
  ...LIST.packs[0],
  rules: [
    { id: "EU-1", severity: "high", description: "Prohibited-practice indicator screening" },
    { id: "EU-2", severity: "medium", description: "Transparency requirement gap check" },
    { id: "EU-3", description: "Human oversight indicator" }, // no severity → medium default
  ],
};

function routeFetch(detailJson, { detailOk = true } = {}) {
  return vi.fn((url) => {
    if (/\/api\/v1\/rules\/packs\/[^/]+$/.test(String(url))) {
      return Promise.resolve({ ok: detailOk, status: detailOk ? 200 : 500, json: () => Promise.resolve(detailJson) });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LIST) });
  });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-006 AC-1 / FND-081: list shows the API's rule_count", () => {
  it("renders 'N rules' from rule_count, never 0-from-missing-array", async () => {
    vi.stubGlobal("fetch", routeFetch(EU_DETAIL));
    render(<RulePacks token="t" />);
    expect(await screen.findByText("3 rules")).toBeInTheDocument();
    expect(screen.getByText("6 rules")).toBeInTheDocument();
    expect(screen.queryByText("0 rules")).not.toBeInTheDocument();
  });
});

describe("STORY-TAB-006 AC-2/AC-4: selecting a pack fetches and renders its rules", () => {
  it("fetches /rules/packs/{framework} and lists rule ids + severities", async () => {
    const user = userEvent.setup();
    const fetchMock = routeFetch(EU_DETAIL);
    vi.stubGlobal("fetch", fetchMock);
    render(<RulePacks token="t" />);

    await user.click(await screen.findByText("EU AI Act"));
    expect(await screen.findByText("EU-1")).toBeInTheDocument();
    expect(screen.getByText("EU-2")).toBeInTheDocument();
    expect(screen.getByText("Prohibited-practice indicator screening")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    // detail URL was the per-framework endpoint
    const detailCall = fetchMock.mock.calls.find(([u]) => /\/rules\/packs\/EU-AI-ACT-2024$/.test(String(u)));
    expect(detailCall).toBeTruthy();
    // AC-4: header metadata + changelog
    expect(screen.getByText(/active/i)).toBeInTheDocument();
    expect(screen.getByText(/Initial release covering Annex III/)).toBeInTheDocument();
  });

  it("AC-5: a rule without severity renders the medium default", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", routeFetch(EU_DETAIL));
    render(<RulePacks token="t" />);
    await user.click(await screen.findByText("EU AI Act"));
    await screen.findByText("EU-3");
    expect(screen.getAllByText("MEDIUM")).toHaveLength(2); // EU-2 + defaulted EU-3
  });

  it("AC-3: detail failure shows an error in the pane; the list stays usable", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", routeFetch({}, { detailOk: false }));
    render(<RulePacks token="t" />);
    await user.click(await screen.findByText("EU AI Act"));
    expect(await screen.findByText(/Failed to load rule pack detail/i)).toBeInTheDocument();
    expect(screen.getByText("NIST AI Risk Management Framework")).toBeInTheDocument();
  });

  it("edge: rapid selection switching — a stale response never overwrites the newer selection", async () => {
    const user = userEvent.setup();
    let resolveEu;
    const euPromise = new Promise((res) => { resolveEu = res; });
    const fetchMock = vi.fn((url) => {
      const u = String(url);
      if (u.endsWith("/rules/packs/EU-AI-ACT-2024")) {
        return euPromise; // slow EU detail
      }
      if (u.endsWith("/rules/packs/NIST-AI-RMF")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ...LIST.packs[1], rules: [{ id: "NIST-1", severity: "low", description: "Govern 1.1 mapping" }] }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LIST) });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<RulePacks token="t" />);

    await user.click(await screen.findByText("EU AI Act"));
    await user.click(screen.getByText("NIST AI Risk Management Framework"));
    expect(await screen.findByText("NIST-1")).toBeInTheDocument();

    // the EU response arrives late — it must NOT replace the NIST detail
    resolveEu({ ok: true, status: 200, json: () => Promise.resolve(EU_DETAIL) });
    await waitFor(() => expect(screen.queryByText("EU-1")).not.toBeInTheDocument());
    expect(screen.getByText("NIST-1")).toBeInTheDocument();
  });
});
