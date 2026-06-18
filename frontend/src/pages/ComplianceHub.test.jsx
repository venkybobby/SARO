import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import ComplianceHub, { canonicalFramework, buildEvfRows } from "./ComplianceHub";

// The EVF card and the Compliance Calendar both render framework labels, so
// queries must be scoped to the EVF card to avoid cross-section collisions.
function evfCard() {
  return screen.getByRole("heading", { name: "EVF Validation Status" }).closest("div");
}

// ── fetch mock: route by URL fragment ────────────────────────────────────────
function routeFetch(routes) {
  return vi.fn((url) => {
    for (const [frag, resp] of Object.entries(routes)) {
      if (url.includes(frag)) {
        const { ok = true, status = 200, json = [] } = resp;
        return Promise.resolve({ ok, status, json: () => Promise.resolve(json) });
      }
    }
    // default: empty OK
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
  });
}

const COVERAGE_3FW = {
  frameworks: [
    { framework: "EU AI Act", coverage_pct: 62.5, last_updated: "2026-06-01" },
    { framework: "NIST AI RMF", coverage_pct: 40.0, last_updated: "2026-05-20" },
    { framework: "ISO 42001", coverage_pct: 75.0, last_updated: null },
  ],
  overall_coverage_pct: 59.2,
  framework_count: 3,
  total_rules: 24,
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-CHUB-001: EVF Validation Status card — real tier data + invariant", () => {
  it("AC-2: canonicalFramework normalizes display strings and enum values both directions", () => {
    expect(canonicalFramework("EU AI Act")).toBe("EU_AI_ACT");
    expect(canonicalFramework("EU_AI_ACT")).toBe("EU_AI_ACT");
    expect(canonicalFramework("NIST AI RMF")).toBe("NIST_AI_RMF");
    expect(canonicalFramework("NIST AI RMF 1.0")).toBe("NIST_AI_RMF");
    expect(canonicalFramework("NIST_AI_RMF")).toBe("NIST_AI_RMF");
    expect(canonicalFramework("ISO 42001")).toBe("ISO_42001");
    expect(canonicalFramework("ISO_42001")).toBe("ISO_42001");
    expect(canonicalFramework("AIGP")).toBe("AIGP");
  });

  it("buildEvfRows: every coverage row carries a tier (never coverage-%-without-tier)", () => {
    const rows = buildEvfRows({
      coverage: COVERAGE_3FW,
      statuses: [{ framework: "EU_AI_ACT", tier: "tier_1", label: "Externally Reviewed", qco_reference: "QCO-1", qco_expiry_date: "2099-01-01" }],
      tierUnavailable: false,
    });
    // all three coverage frameworks present and each has a tier
    expect(rows.length).toBeGreaterThanOrEqual(3);
    for (const r of rows) {
      expect(r.tier).toBeTruthy();
    }
    const eu = rows.find((r) => canonicalFramework(r.label) === "EU_AI_ACT");
    expect(eu.tier).toBe("tier_1");
    const nist = rows.find((r) => canonicalFramework(r.label) === "NIST_AI_RMF");
    expect(nist.tier).toBe("tier_3"); // no status → default tier_3
  });

  it("buildEvfRows: framework present in status but absent from coverage still surfaces (tier badge only)", () => {
    const rows = buildEvfRows({
      coverage: { frameworks: [] },
      statuses: [{ framework: "AIGP", tier: "tier_2", label: "Under review" }],
      tierUnavailable: false,
    });
    const aigp = rows.find((r) => canonicalFramework(r.label) === "AIGP");
    expect(aigp).toBeTruthy();
    expect(aigp.coveragePct).toBeNull();
    expect(aigp.tier).toBe("tier_2");
  });

  it("buildEvfRows: expired Tier 1 is downgraded to a warning, never green/validated", () => {
    const rows = buildEvfRows({
      coverage: { frameworks: [{ framework: "EU AI Act", coverage_pct: 80 }] },
      statuses: [{ framework: "EU_AI_ACT", tier: "tier_1", label: "Externally Reviewed", qco_reference: "QCO-X", qco_expiry_date: "2000-01-01" }],
      tierUnavailable: false,
    });
    const eu = rows[0];
    expect(eu.tier).not.toBe("tier_1");
    expect(eu.warning).toBe(true);
  });

  it("buildEvfRows: tierUnavailable forces every coverage row to tier_3", () => {
    const rows = buildEvfRows({ coverage: COVERAGE_3FW, statuses: [], tierUnavailable: true });
    expect(rows.length).toBe(3);
    for (const r of rows) expect(r.tier).toBe("tier_3");
  });

  it("AC-1: framework label reads fw.framework and is never blank", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [{ framework: "EU_AI_ACT", tier: "tier_3", label: "Internal" }] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    await screen.findByText("62.5%"); // wait for coverage data in the card
    const card = within(evfCard());
    expect(card.getByText("EU AI Act")).toBeInTheDocument();
    expect(card.getByText("NIST AI RMF")).toBeInTheDocument();
    expect(card.getByText("ISO 42001")).toBeInTheDocument();
  });

  it("AC-3: a coverage framework with no resolved tier shows the Tier 3 INTERNAL ONLY badge", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    await screen.findByText("62.5%");
    // each of the 3 coverage cards must show an INTERNAL ONLY tier badge
    const badges = within(evfCard()).getAllByText(/INTERNAL ONLY/);
    expect(badges.length).toBe(3);
  });

  it("AC-5: tier_1 status renders EXTERNALLY REVIEWED badge with QCO ref", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: { frameworks: [{ framework: "EU AI Act", coverage_pct: 90, last_updated: "2026-06-01" }] } },
      "validation-status": { json: [{ framework: "EU_AI_ACT", tier: "tier_1", label: "Externally Reviewed", qco_reference: "QCO-EU-1", qco_expiry_date: "2099-01-01" }] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText(/EXTERNALLY REVIEWED/)).toBeInTheDocument();
    expect(screen.getByText(/QCO-EU-1/)).toBeInTheDocument();
  });

  it("AC-4: validation-status 403 → all Tier 3 + unavailable note, no 'validated/externally reviewed' wording", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { ok: false, status: 403, json: { detail: "forbidden" } },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    await screen.findByText("62.5%");
    expect(await screen.findByText(/treated as internal only/i)).toBeInTheDocument();
    const badges = within(evfCard()).getAllByText(/INTERNAL ONLY/);
    expect(badges.length).toBe(3);
    expect(within(evfCard()).queryByText(/EXTERNALLY REVIEWED/)).not.toBeInTheDocument();
    expect(screen.queryByText(/validated/i)).not.toBeInTheDocument();
  });
});

describe("STORY-CHUB-002: Recent Audits access — visible error, not silent empty (AC-5)", () => {
  it("AC-5: a failed audits fetch (403) shows a visible error, not the empty state", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { ok: false, status: 403, json: { detail: "forbidden" } },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText(/Could not load audits/i)).toBeInTheDocument();
    expect(screen.queryByText("No audits yet.")).not.toBeInTheDocument();
  });

  it("a successful empty audits fetch still shows the legitimate empty state", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText("No audits yet.")).toBeInTheDocument();
    expect(screen.queryByText(/Could not load audits/i)).not.toBeInTheDocument();
  });
});

describe("STORY-CHUB-003 / FND-026: Recent Audits risk-score field mapping", () => {
  function renderWithAudits(audits) {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: audits },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
  }

  it("AC-2: overall_risk_score=0.41 renders 41 (amber), not '—'", async () => {
    renderWithAudits([{ id: "aaaaaaaaaaaa1", status: "completed", overall_risk_score: 0.41 }]);
    expect(await screen.findByText("41")).toBeInTheDocument();
  });

  it("AC-3: null/absent risk score renders '—', never a 0 badge", async () => {
    renderWithAudits([{ id: "bbbbbbbbbbbb2", status: "completed", overall_risk_score: null }]);
    const row = (await screen.findByText(/bbbbbbbbbbbb/)).closest("tr");
    expect(within(row).getByText("—")).toBeInTheDocument();
    expect(within(row).queryByText("0")).not.toBeInTheDocument();
  });

  it("edge: genuine overall_risk_score=0 renders a '0' badge (distinct from null)", async () => {
    renderWithAudits([{ id: "cccccccccccc3", status: "completed", overall_risk_score: 0 }]);
    const row = (await screen.findByText(/cccccccccccc/)).closest("tr");
    expect(within(row).getByText("0")).toBeInTheDocument();
  });

  it("AC-1: legacy a.risk_score fallback still renders when overall_risk_score absent", async () => {
    renderWithAudits([{ id: "dddddddddddd4", status: "completed", risk_score: 0.9 }]);
    expect(await screen.findByText("90")).toBeInTheDocument();
  });
});
