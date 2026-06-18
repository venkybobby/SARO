import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ComplianceHub, { canonicalFramework, buildEvfRows, mostRecentLastUpdated } from "./ComplianceHub";

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
        return Promise.resolve({
          ok,
          status,
          json: () => Promise.resolve(json),
          blob: () => Promise.resolve({ size: 1, type: "application/octet-stream" }),
        });
      }
    }
    // default: empty OK
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
      blob: () => Promise.resolve({ size: 0 }),
    });
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

describe("STORY-CHUB-005: overall coverage headline + provenance", () => {
  it("mostRecentLastUpdated returns the latest date, or null when all null", () => {
    expect(mostRecentLastUpdated([{ last_updated: "2026-05-01" }, { last_updated: "2026-06-10" }, { last_updated: null }])).toBe("2026-06-10");
    expect(mostRecentLastUpdated([{ last_updated: null }, {}])).toBeNull();
    expect(mostRecentLastUpdated([])).toBeNull();
  });

  it("AC-1/AC-2: renders overall %, framework/rule counts and the most-recent provenance", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText("59.2%")).toBeInTheDocument();
    expect(screen.getByText("Matrix coverage")).toBeInTheDocument();
    expect(screen.getByText(/3 frameworks · 24 rules/)).toBeInTheDocument();
    expect(screen.getByText(/as of 2026-06-01/)).toBeInTheDocument();
  });

  it("AC-1: label says 'Matrix coverage', never 'compliant'/'validated'", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    await screen.findByText("59.2%");
    expect(screen.queryByText(/compliant/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/validated/i)).not.toBeInTheDocument();
  });

  it("edge: all last_updated null → 'as of —'", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: { frameworks: [{ framework: "EU AI Act", coverage_pct: 50, last_updated: null }], overall_coverage_pct: 50, framework_count: 1, total_rules: 3 } },
      "validation-status": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText(/as of —/)).toBeInTheDocument();
  });

  it("edge: total_rules=0 → 'No matrix data yet', not '0% compliant'", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: { frameworks: [], overall_coverage_pct: 0, framework_count: 0, total_rules: 0 } },
      "validation-status": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText("No matrix data yet")).toBeInTheDocument();
  });

  it("AC-4: coverage error → headline shows '—', never a fabricated number", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { ok: false, status: 500, json: { detail: "boom" } },
      "validation-status": { json: [] },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect((await screen.findAllByText(/Coverage data unavailable/)).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });
});

describe("STORY-CHUB-006: actions + drill-throughs", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
  });

  function setup(extraRoutes = {}, onNavigate) {
    const fetchMock = routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [{ id: "audit-xyz-123", status: "completed", overall_risk_score: 0.5 }] },
      ...extraRoutes,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ComplianceHub token="t" tenantId="ten-1" onNavigate={onNavigate} />);
    return fetchMock;
  }

  it("AC-1: Export matrix (CSV) issues GET /compliance-matrix/export", async () => {
    const user = userEvent.setup();
    const fetchMock = setup();
    await screen.findByText("59.2%");
    await user.click(screen.getByRole("button", { name: /Export matrix \(CSV\)/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/compliance-matrix/export"), expect.anything())
    );
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("AC-2: Generate board report issues GET /risk/board-export", async () => {
    const user = userEvent.setup();
    const fetchMock = setup();
    await screen.findByText(/audit-xyz-12/);
    await user.click(screen.getByRole("button", { name: /Generate board report/ }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/v1/risk/board-export"), expect.anything())
    );
  });

  it("AC-5 / 413: export failure shows inline error and downloads nothing", async () => {
    const user = userEvent.setup();
    setup({
      "/compliance-matrix/export": { ok: false, status: 413, json: { detail: { message: "Export exceeds the 50,000 row limit. Apply filters to reduce the dataset." } } },
    });
    await screen.findByText("59.2%");
    await user.click(screen.getByRole("button", { name: /Export matrix \(CSV\)/ }));
    expect(await screen.findByText(/Apply filters to reduce the dataset/)).toBeInTheDocument();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it("AC-3: clicking a framework card navigates to the matrix filtered by framework", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    setup({}, onNavigate);
    await screen.findByText("59.2%");
    await user.click(within(evfCard()).getByText("EU AI Act"));
    expect(onNavigate).toHaveBeenCalledWith("coverage_gap", { framework: "EU AI Act" });
  });

  it("AC-4: clicking an audit row navigates to its TRACE view by audit id", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    setup({}, onNavigate);
    await user.click(await screen.findByText(/audit-xyz-12/));
    expect(onNavigate).toHaveBeenCalledWith("trace_view", "audit-xyz-123");
  });

  it("edge: board report is disabled when there are no audits (No data)", async () => {
    setup({ "/api/v1/audits": { json: [] } });
    await screen.findByText("59.2%");
    expect(screen.getByRole("button", { name: /Generate board report/ })).toBeDisabled();
  });
});

describe("STORY-CHUB-004: Readiness Checklist hydrates from endpoint", () => {
  const READINESS = {
    items: [
      { key: "dpa_in_place", label: "Data processing agreements in place", kind: "manual", completed: true, editable: true, source: null },
      { key: "ai_systems_registered", label: "AI systems registered in inventory", kind: "derived", completed: false, editable: false, source: "Derived from AIMS inventory records (ISO 42001 evidence)" },
      { key: "risk_assessments_completed", label: "Risk assessments completed for high-risk systems", kind: "manual", completed: false, editable: true, source: null },
    ],
    completed: 1,
    total: 3,
  };

  function setup(readiness = READINESS) {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [] },
      "/api/v1/compliance/readiness": { json: readiness },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
  }

  it("AC-4: checked state hydrates from the endpoint (not in-memory defaults)", async () => {
    setup();
    const dpa = await screen.findByLabelText(/Data processing agreements in place/);
    expect(dpa).toBeChecked();
    const risk = screen.getByLabelText(/Risk assessments completed/);
    expect(risk).not.toBeChecked();
  });

  it("AC-3: derived items are read-only with a source tooltip", async () => {
    setup();
    const ai = await screen.findByLabelText(/AI systems registered in inventory/);
    expect(ai).toBeDisabled();
    expect(screen.getByText(/AI systems registered in inventory/).closest("label"))
      .toHaveAttribute("title", expect.stringContaining("AIMS inventory"));
  });

  it("AC-4: completion counter reflects persisted + derived state", async () => {
    setup();
    expect(await screen.findByText("1/3 complete")).toBeInTheDocument();
  });

  it("edge: a derived item with unknown source state shows 'unknown', not checked", async () => {
    setup({
      items: [
        { key: "ai_systems_registered", label: "AI systems registered in inventory", kind: "derived", completed: null, editable: false, source: "AIMS" },
      ],
      completed: 0,
      total: 1,
    });
    const ai = await screen.findByLabelText(/AI systems registered in inventory/);
    expect(ai).not.toBeChecked();
    expect(ai).toBeDisabled();
    expect(screen.getByText(/unknown/)).toBeInTheDocument();
  });

  it("toggling a manual item PUTs to the persistence endpoint", async () => {
    const user = userEvent.setup();
    const fetchMock = routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [] },
      "/api/v1/compliance/readiness": { json: READINESS },
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    const risk = await screen.findByLabelText(/Risk assessments completed/);
    await user.click(risk);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/compliance/readiness/risk_assessments_completed"),
        expect.objectContaining({ method: "PUT" })
      )
    );
  });
});

describe("STORY-CHUB-007: design-system refactor", () => {
  function setup() {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [] },
      "/api/v1/compliance/readiness": { json: { items: [], completed: 0, total: 0 } },
    }));
    return render(<ComplianceHub token="t" tenantId="ten-1" />);
  }

  it("AC-1: renders a PageHeader with the 'Compliance Hub' title and no emoji in headings", async () => {
    setup();
    expect(await screen.findByRole("heading", { name: "Compliance Hub" })).toBeInTheDocument();
    // headings must not carry the old emoji prefixes
    for (const h of screen.getAllByRole("heading")) {
      expect(h.textContent).not.toMatch(/[🏛️📅]/u);
    }
    // the Compliance Calendar heading is now plain text (emoji removed)
    expect(screen.getByRole("heading", { name: "Compliance Calendar" })).toBeInTheDocument();
  });

  it("AC-2: no hardcoded hex colors or system-ui literals remain in rendered styles", async () => {
    const { container } = setup();
    await screen.findByText("59.2%");
    const html = container.innerHTML;
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/); // no hex color literals
    expect(html).not.toMatch(/system-ui/);
  });

  it("AC-4: disclaimer footer wording is preserved verbatim", async () => {
    setup();
    expect(
      await screen.findByText(/This report is audit evidence generated by SARO v8\.0\.0\./)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Human review and sign-off by qualified personnel is required before any regulatory submission\./)
    ).toBeInTheDocument();
  });
});

describe("STORY-CHUB-008: loading skeletons + visible error states", () => {
  it("AC-1: each section shows a Skeleton while its data is loading", () => {
    // fetch never resolves → every section stays in the loading state
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(screen.getByTestId("coverage-headline-loading")).toBeInTheDocument();
    expect(screen.getByTestId("evf-loading")).toBeInTheDocument();
    expect(screen.getByTestId("audits-loading")).toBeInTheDocument();
    expect(screen.getByTestId("readiness-loading")).toBeInTheDocument();
    expect(screen.getByTestId("calendar-loading")).toBeInTheDocument();
  });

  it("AC-2/AC-4: a rejected audits fetch shows a section error with a retry that re-fetches only that section", async () => {
    const user = userEvent.setup();
    let auditsCalls = 0;
    let coverageCalls = 0;
    const fetchMock = vi.fn((url, opts) => {
      if (url.includes("/api/v1/audits")) {
        auditsCalls += 1;
        if (auditsCalls === 1) return Promise.reject(new Error("boom"));
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      }
      if (url.includes("/compliance-matrix/coverage")) {
        coverageCalls += 1;
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COVERAGE_3FW) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ComplianceHub token="t" tenantId="ten-1" />);

    expect(await screen.findByText(/Could not load audits/)).toBeInTheDocument();
    const coverageCallsBeforeRetry = coverageCalls;
    await user.click(screen.getByRole("button", { name: "Retry" }));

    // audits re-fetched; coverage NOT re-fetched by the audits retry
    await waitFor(() => expect(auditsCalls).toBe(2));
    expect(coverageCalls).toBe(coverageCallsBeforeRetry);
    expect(await screen.findByText("No audits yet.")).toBeInTheDocument();
  });

  it("AC-3: a successful empty fetch shows the empty state, distinct from the error state", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [] },
      "/api/v1/compliance/readiness": { json: { items: [], completed: 0, total: 0 } },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText("No audits yet.")).toBeInTheDocument();
    expect(screen.queryByText(/Could not load audits/)).not.toBeInTheDocument();
  });

  it("edge: partial failure isolates — audits 403 errors while EVF still renders", async () => {
    vi.stubGlobal("fetch", routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { ok: false, status: 403, json: { detail: "forbidden" } },
      "/api/v1/compliance/readiness": { json: { items: [], completed: 0, total: 0 } },
    }));
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    expect(await screen.findByText(/Could not load audits/)).toBeInTheDocument();
    // EVF card still renders its frameworks normally
    expect(within(evfCard()).getByText("EU AI Act")).toBeInTheDocument();
  });
});

describe("STORY-CHUB-009: outgoing requests carry only backend-honored params", () => {
  it("AC-1/AC-2: /coverage drops tenant_id & window; /audits drops tenant_id & sort", async () => {
    const fetchMock = routeFetch({
      "/compliance-matrix/coverage": { json: COVERAGE_3FW },
      "validation-status": { json: [] },
      "/api/v1/audits": { json: [] },
      "/api/v1/compliance/readiness": { json: { items: [], completed: 0, total: 0 } },
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ComplianceHub token="t" tenantId="ten-1" />);
    await screen.findByText("59.2%");

    const urls = fetchMock.mock.calls.map((c) => c[0]);
    const coverageUrl = urls.find((u) => u.includes("/compliance-matrix/coverage"));
    const auditsUrl = urls.find((u) => u.includes("/api/v1/audits"));

    expect(coverageUrl).toBeTruthy();
    expect(coverageUrl).not.toMatch(/tenant_id/);
    expect(coverageUrl).not.toMatch(/window/);

    expect(auditsUrl).toBeTruthy();
    expect(auditsUrl).not.toMatch(/tenant_id/);
    expect(auditsUrl).not.toMatch(/sort/);
    expect(auditsUrl).toMatch(/limit=10/); // limit IS honored by the backend
  });
});
