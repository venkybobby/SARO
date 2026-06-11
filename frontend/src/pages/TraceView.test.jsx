import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import TraceView from "./TraceView";

const TRACE = { audit_id: "audit-123456789", status: "pass", risk_score: 0.42, steps: [] };
const AUDIT = { rule_pack_version: "3", created_at: "2026-01-01T00:00:00Z" };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url) => {
    if (url === "/api/v1/traces/audit-123456789") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(TRACE) });
    }
    if (url === "/api/v1/audits/audit-123456789") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(AUDIT) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
  }));
});

describe("TraceView audit metadata enrichment (regression: ESLint flat-config no-undef)", () => {
  it("loads the trace and the audit report (rule pack badge) without throwing ReferenceError", async () => {
    render(<TraceView token="t" initialAuditId="audit-123456789" />);

    await waitFor(() => expect(screen.getByText(/Rule Pack/)).toBeInTheDocument());
    expect(screen.getByText(/Rule Pack/).textContent).toContain("v3");
  });
});
