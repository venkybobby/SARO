/**
 * STORY-TAB-007 / FND-082 — AIMS renders only real registry fields.
 *
 * Contract (routers/aims.py, post-fix): models carry
 *   {model_id, name, version, effective_date, owner_email,
 *    linked_audit_count, created_at}
 * — no risk_tier / lifecycle_stage / framework_coverage (those were hardcoded
 * constants), and the frontend must not read vendor / risk_category /
 * last_audit_date (never returned).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Aims from "./Aims";

const MODELS = {
  models: [
    {
      model_id: "11111111-1111-1111-1111-111111111111",
      name: "Claims triage model",
      version: "2.1.0",
      effective_date: "2026-05-01T00:00:00+00:00",
      owner_email: "owner@tenant-a.test",
      linked_audit_count: 2,
      created_at: "2026-04-20T12:00:00+00:00",
    },
    {
      model_id: "22222222-2222-2222-2222-222222222222",
      name: "Sparse model",
      version: "1.0.0",
      effective_date: null,
      owner_email: "owner2@tenant-a.test",
      linked_audit_count: 0,
      created_at: null,
    },
  ],
  total: 2,
  tenant_id: "t",
  note: "Model registry derived from AIMS document lifecycle records. Evidence-based - human review required for classification decisions.",
};

function ok(json) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(json) });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-007 AC-2/AC-3 / FND-082: cards render real fields, no fabricated badges", () => {
  it("shows name, version, owner, effective date, and linked-audit count", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(MODELS)));
    render(<Aims token="t" tenantId="tid" />);

    expect(await screen.findByText("Claims triage model")).toBeInTheDocument();
    expect(screen.getByText(/Version: 2\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/Owner: owner@tenant-a\.test/)).toBeInTheDocument();
    expect(screen.getByText(/Effective: 2026-05-01/)).toBeInTheDocument();
    expect(screen.getByText(/2 linked audits/)).toBeInTheDocument();
  });

  it("renders NO stage badge and no vendor/risk-category/last-audit rows", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(MODELS)));
    const { container } = render(<Aims token="t" tenantId="tid" />);
    await screen.findByText("Claims triage model");
    expect(screen.queryByText("PRODUCTION")).not.toBeInTheDocument();
    expect(screen.queryByText(/Vendor:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Risk Category:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Last Audit:/)).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/undefined|null/);
  });

  it("keeps the ISO 42001 evidence-language footer (compliance-guard NFR)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(MODELS)));
    render(<Aims token="t" tenantId="tid" />);
    await screen.findByText("Claims triage model");
    expect(screen.getAllByText(/Audit evidence for ISO 42001 document lifecycle review/).length).toBeGreaterThan(0);
  });

  it("edge: sparse model (null dates, 0 audits) renders cleanly", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok(MODELS)));
    render(<Aims token="t" tenantId="tid" />);
    expect(await screen.findByText("Sparse model")).toBeInTheDocument();
    expect(screen.getByText(/0 linked audits/)).toBeInTheDocument();
  });
});

describe("STORY-TAB-007 AC-4: empty state names the concrete next action", () => {
  it("points at the AIMS documents API / Compliance Hub, not a bare 'register via the API'", async () => {
    vi.stubGlobal("fetch", vi.fn(() => ok({ models: [], total: 0, tenant_id: "t", note: "" })));
    render(<Aims token="t" tenantId="tid" />);
    const empty = await screen.findByText(/No AI models registered/);
    expect(empty.textContent).toMatch(/aims\/documents|Compliance Hub/i);
  });
});

describe("STORY-TAB-007: error state", () => {
  it("non-2xx renders an error banner", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
    render(<Aims token="t" tenantId="tid" />);
    expect(await screen.findByText(/Failed to load model inventory/i)).toBeInTheDocument();
  });
});
