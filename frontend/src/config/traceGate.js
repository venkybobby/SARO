// STORY-TRACE-005: single source of truth for the ADR-004 "How SARO Reasons"
// TRACE View gate.
//
// ADR-004 ("TRACE View Gate"): the "How SARO Reasons" transparency document must
// be authored/approved before any enterprise demo of the TRACE view exposes full
// reasoning detail. This flag records whether that document is published.
//
// Default-deny: when the flag is unset/unknown, the document is treated as NOT
// ready (the gate is ON for enterprise/demo sessions). Ops flips it to "true" once
// the methodology doc is approved.
export const TRACE_METHODOLOGY_READY =
  String(import.meta.env?.VITE_TRACE_METHODOLOGY_READY ?? "")
    .trim()
    .toLowerCase() === "true";
