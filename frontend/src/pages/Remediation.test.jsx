/**
 * STORY-TAB-001 / FND-073 — Remediation tab response-contract pin.
 *
 * The backend contract being pinned (routers/remediation.py):
 *   GET  /api/v1/remediation                       → {traces:[...], total, page, page_size, pages}
 *   PATCH /api/v1/remediation/traces/{id}/remediate ← {remediation_note} (422 if blank)
 *
 * Pre-fix, the component read `d.items` (never present → permanent empty state)
 * and PATCHed /api/v1/remediation/{id}/complete (no such route).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Remediation from "./Remediation";

const TRACE_FULL = {
  id: "11111111-1111-1111-1111-111111111111",
  audit_id: "aaaa1111-1111-1111-1111-111111111111",
  check_name: "PII: email address detected",
  gate_name: "Gate 2 — PII",
  result: "fail",
  reason: "Raw email address present in output",
  remediation_hint: "Mask or remove the email address before release.",
  regulation_ref: "EU-AI-ACT-2024 Art. 10",
  effort_estimate: "Medium",
  domain: "PII",
  created_at: "2026-07-20T10:00:00Z",
};

const TRACE_SPARSE = {
  id: "22222222-2222-2222-2222-222222222222",
  audit_id: "aaaa1111-1111-1111-1111-111111111111",
  check_name: "Toxicity threshold exceeded",
  gate_name: "Gate 1",
  result: "warn",
  reason: null,
  remediation_hint: null,
  regulation_ref: null,
  effort_estimate: null,
  domain: "toxicity",
  created_at: null,
};

function listResponse(traces, total = traces.length) {
  return { traces, total, page: 1, page_size: 50, pages: 1 };
}

function mockFetchOnce(routes) {
  // routes: array of {match: (url, opts) => bool, ok, status, json}
  return vi.fn((url, opts = {}) => {
    for (const r of routes) {
      if (r.match(url, opts)) {
        return Promise.resolve({
          ok: r.ok !== false,
          status: r.status || 200,
          json: () => Promise.resolve(r.json ?? {}),
        });
      }
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(listResponse([])) });
  });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("STORY-TAB-001 AC-1 / FND-073: traces from the real response shape render", () => {
  it("renders a card per trace and no empty state when traces is non-empty", async () => {
    const fetchMock = mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([TRACE_FULL, TRACE_SPARSE]) },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<Remediation token="t" tenantId="tid" />);

    expect(await screen.findByText("PII: email address detected")).toBeInTheDocument();
    expect(screen.getByText("Toxicity threshold exceeded")).toBeInTheDocument();
    expect(screen.queryByText(/No open remediation actions/)).not.toBeInTheDocument();
  });
});

describe("STORY-TAB-001 AC-2: real API fields render", () => {
  it("shows reason, guidance, result badge, effort, and regulation ref", async () => {
    vi.stubGlobal("fetch", mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([TRACE_FULL]) },
    ]));
    render(<Remediation token="t" tenantId="tid" />);

    expect(await screen.findByText("Raw email address present in output")).toBeInTheDocument();
    expect(screen.getByText(/Mask or remove the email address/)).toBeInTheDocument();
    expect(screen.getByText("FAIL")).toBeInTheDocument();
    expect(screen.getByText(/Effort: Medium/)).toBeInTheDocument();
    expect(screen.getByText(/EU-AI-ACT-2024 Art\. 10/)).toBeInTheDocument();
  });

  it("warn result renders a WARN badge", async () => {
    vi.stubGlobal("fetch", mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([TRACE_SPARSE]) },
    ]));
    render(<Remediation token="t" tenantId="tid" />);
    expect(await screen.findByText("WARN")).toBeInTheDocument();
  });
});

describe("STORY-TAB-001 AC-3: remediate flow hits the canonical endpoint with a note", () => {
  it("Mark Complete reveals a note input; confirm PATCHes /traces/{id}/remediate and reloads", async () => {
    const user = userEvent.setup();
    let listCalls = 0;
    const fetchMock = vi.fn((url, opts = {}) => {
      if ((opts.method || "GET") === "PATCH") {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ id: TRACE_FULL.id, is_remediated: true }) });
      }
      listCalls += 1;
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(listCalls === 1 ? listResponse([TRACE_FULL]) : listResponse([])),
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Remediation token="t" tenantId="tid" />);

    await user.click(await screen.findByRole("button", { name: /Mark Complete/i }));
    const noteBox = await screen.findByPlaceholderText(/note/i);
    await user.type(noteBox, "Masked the address; re-scanned clean.");
    await user.click(screen.getByRole("button", { name: /Confirm/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(([, o]) => o?.method === "PATCH");
      expect(patchCall).toBeTruthy();
      const [url, opts] = patchCall;
      expect(url).toBe(`/api/v1/remediation/traces/${TRACE_FULL.id}/remediate`);
      expect(JSON.parse(opts.body)).toEqual({ remediation_note: "Masked the address; re-scanned clean." });
    });
    // list reloaded and the trace is gone
    await waitFor(() => {
      expect(screen.queryByText("PII: email address detected")).not.toBeInTheDocument();
    });
    expect(await screen.findByText(/No open remediation actions/)).toBeInTheDocument();
  });

  it("does not PATCH while the note is blank (backend would 422)", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([TRACE_FULL]) },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<Remediation token="t" tenantId="tid" />);

    await user.click(await screen.findByRole("button", { name: /Mark Complete/i }));
    const confirm = await screen.findByRole("button", { name: /Confirm/i });
    await user.click(confirm);
    expect(fetchMock.mock.calls.every(([, o]) => (o?.method || "GET") !== "PATCH")).toBe(true);
  });

  it("edge: a failed PATCH keeps the card and surfaces an error", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((url, opts = {}) => {
      if ((opts.method || "GET") === "PATCH") {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: "boom" }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(listResponse([TRACE_FULL])) });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Remediation token="t" tenantId="tid" />);

    await user.click(await screen.findByRole("button", { name: /Mark Complete/i }));
    await user.type(await screen.findByPlaceholderText(/note/i), "note text");
    await user.click(screen.getByRole("button", { name: /Confirm/i }));

    expect(await screen.findByText(/Failed to mark as remediated/i)).toBeInTheDocument();
    expect(screen.getByText("PII: email address detected")).toBeInTheDocument();
  });
});

describe("STORY-TAB-001 AC-4/AC-5: empty vs error states", () => {
  it("total === 0 renders the empty state", async () => {
    vi.stubGlobal("fetch", mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([]) },
    ]));
    render(<Remediation token="t" tenantId="tid" />);
    expect(await screen.findByText(/No open remediation actions/)).toBeInTheDocument();
  });

  it("non-2xx renders the error banner, not the empty state", async () => {
    vi.stubGlobal("fetch", mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), ok: false, status: 500, json: {} },
    ]));
    render(<Remediation token="t" tenantId="tid" />);
    expect(await screen.findByText(/Failed to load remediations/)).toBeInTheDocument();
    expect(screen.queryByText(/No open remediation actions/)).not.toBeInTheDocument();
  });
});

describe("STORY-TAB-001 edge cases", () => {
  it("sparse trace renders without 'undefined'/'null' text and without optional rows", async () => {
    vi.stubGlobal("fetch", mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([TRACE_SPARSE]) },
    ]));
    const { container } = render(<Remediation token="t" tenantId="tid" />);
    await screen.findByText("Toxicity threshold exceeded");
    expect(container.textContent).not.toMatch(/undefined|null/);
    expect(screen.queryByText(/Effort:/)).not.toBeInTheDocument();
  });

  it("shows 'showing N of M' when total exceeds the page", async () => {
    vi.stubGlobal("fetch", mockFetchOnce([
      { match: (u) => u.includes("/api/v1/remediation"), json: listResponse([TRACE_FULL, TRACE_SPARSE], 120) },
    ]));
    render(<Remediation token="t" tenantId="tid" />);
    expect(await screen.findByText(/showing 2 of 120/i)).toBeInTheDocument();
  });
});
