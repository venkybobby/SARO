/**
 * Knowledge Portal — single searchable home for all SARO documentation.
 *
 * Consolidates: HowSaroReasons, GovernanceDocs, Governance Trust,
 * ClaimsMatrix (reference), DPA / IR Plan.
 *
 * Each article is a static knowledge card. Nothing here is operational —
 * it's reference material that previously cluttered the sidebar.
 */
import React, { useState, useMemo } from "react";
import { Search, BookOpen, Shield, FileText, AlertTriangle, Cpu, ExternalLink } from "lucide-react";
import { PageHeader } from "../components/ui/index.jsx";

const ARTICLES = [
  // ── How SARO Reasons ─────────────────────────────────────────────────────
  {
    id: "how-saro-reasons",
    category: "Engine",
    title: "How SARO Reasons",
    summary: "DIR formula, 4-gate pipeline, SHAP explainability, non-negotiables.",
    icon: Cpu,
    content: [
      {
        heading: "DIR Formula",
        body: "SARO computes a risk score via the DIR (Detection → Interpret → Remediate) formula. The raw score is an integer 0–100. A score of 0 means no risk indicators detected; 100 means maximum risk concentration across all four gates.",
      },
      {
        heading: "Gate 1 — Batch Validation",
        body: "Validates input meets statistical requirements (min 50 samples per internal SARO heuristic — not a regulatory requirement from EU AI Act Art. 10 or NIST MAP 2.3). Checks data quality and completeness before scoring begins.",
      },
      {
        heading: "Gate 2 — Fairness Analysis",
        body: "Computes statistical parity and disparity metrics across protected attributes. Uses Fisher's exact test for group fairness detection. Evidence supporting NIST AI RMF Measure 2.5 — human review required.",
      },
      {
        heading: "Gate 3 — Drift Detection",
        body: "Runs Kolmogorov-Smirnov (KS) test against baseline distributions. Triggers circuit breaker at 2σ deviation threshold. An auto-incident is created when drift exceeds 2σ. Human must review and clear.",
      },
      {
        heading: "Gate 4 — Compliance Mapping",
        body: "Maps scan findings to EU AI Act, NIST AI RMF, ISO 42001, and AIGP evidence categories. SARO provides evidence for human reviewers — it does not certify compliance.",
      },
      {
        heading: "SHAP Explainability",
        body: "SARO uses SHAP (SHapley Additive exPlanations) values to attribute each point of the risk score to specific rule contributions. This enables auditors to understand why a score was produced. Evidence for human auditor review.",
      },
      {
        heading: "Non-Negotiables",
        body: "SARO (1) accepts only prompt + raw_output — never calls external AI models. (2) Returns only risk score, TRACE timeline, remediation guidance. (3) Never writes to client systems. (4) Never certifies compliance — evidence support only. (5) Human-in-the-loop always required.",
      },
    ],
  },

  // ── Claims Matrix ─────────────────────────────────────────────────────────
  {
    id: "claims-matrix",
    category: "Compliance",
    title: "What SARO Claims (and What It Does Not)",
    summary: "Decision matrix: SARO does / does not do. Approved language guide.",
    icon: Shield,
    content: [
      {
        heading: "Risk Assessment",
        body: "SARO does: Computes 0–100 risk score from prompt + output.\nSARO does NOT: Determine if an AI system is 'safe' or 'compliant'.\nApproved language: 'SARO scored this output at {score}/100'",
      },
      {
        heading: "NIST AI RMF",
        body: "SARO does: Maps findings to RMF function areas (Govern, Map, Measure, Manage).\nSARO does NOT: Assert RMF conformance.\nApproved language: 'Evidence supporting NIST AI RMF Measure 2.5'",
      },
      {
        heading: "EU AI Act",
        body: "SARO does: Identifies characteristics associated with high-risk system categories.\nSARO does NOT: Classify a system as high-risk under EU law.\nApproved language: 'Indicators consistent with EU AI Act high-risk criteria'",
      },
      {
        heading: "ISO 42001",
        body: "SARO does: Links scan records to document lifecycle stages.\nSARO does NOT: Issue ISO 42001 certificates.\nApproved language: 'Audit evidence for ISO 42001 document lifecycle review'",
      },
      {
        heading: "AIGP",
        body: "SARO does: Supports human reviewer workflows.\nSARO does NOT: Auto-certify under AIGP.\nApproved language: 'Evidence package for AIGP-certified human reviewer'",
      },
      {
        heading: "EVF Validation Status",
        body: "Current status (2026-06-02): No framework claim has completed External SME Validation (EVF). All four frameworks are in Internal Review Only state. No external compliance claim may be made until a Qualified Compliance Opinion (QCO) is issued.",
      },
    ],
  },

  // ── DPA & Governance ─────────────────────────────────────────────────────
  {
    id: "dpa-governance",
    category: "Governance",
    title: "DPA & Data Governance",
    summary: "Data Processing Agreement template, sub-processors, retention policy.",
    icon: FileText,
    content: [
      {
        heading: "Data Processing Agreement (DPA)",
        body: "SARO provides a DPA template for GDPR Art. 28 compliance. The DPA covers: scope of processing, data subject categories, technical and organisational measures, sub-processor obligations, and data retention.",
        link: { label: "Download DPA Template", href: "/api/v1/governance/dpa-template" },
      },
      {
        heading: "Sub-Processors",
        body: "SARO maintains a list of all sub-processors used in the delivery of the service. Sub-processors are reviewed quarterly. Customers are notified of changes with 30 days notice.",
        link: { label: "View Sub-Processors", href: "/api/v1/governance/sub-processors" },
      },
      {
        heading: "Retention Policy",
        body: "Scan records (Audit + TRACE) are retained for 7 years by default to support regulatory audit obligations. Tenants may configure shorter retention periods via the Settings screen. Deletion is irreversible.",
      },
    ],
  },

  // ── Incident Response ─────────────────────────────────────────────────────
  {
    id: "ir-plan",
    category: "Governance",
    title: "Incident Response Plan",
    summary: "IR phases, escalation paths, SARO's role during AI incidents.",
    icon: AlertTriangle,
    content: [
      {
        heading: "Phase 1 — Detection",
        body: "SARO auto-creates incidents when drift exceeds 2σ (KS-test threshold). Manual incidents can be created by Risk Officers via the Risk Register. All incidents are logged to the immutable TRACE chain.",
      },
      {
        heading: "Phase 2 — Containment",
        body: "SARO provides evidence packages to support containment decisions. SARO never automatically stops or modifies AI systems — human decision required. SARO's read-only posture is preserved throughout.",
      },
      {
        heading: "Phase 3 — Investigation",
        body: "Use TRACE View to examine the 6-step pipeline timeline for any affected audit. Exportable evidence packages are generated for forensic review. Hash-chain integrity is verifiable via SHA-256.",
      },
      {
        heading: "Phase 4 — Recovery",
        body: "Remediation guidance is generated by SARO's engine as evidence for human reviewers. Recovery actions must be approved and executed by the human team. SARO does not write to client systems.",
      },
      {
        heading: "Phase 5 — Post-Incident",
        body: "SARO generates a post-incident TRACE record linking all evidence. This record is available for regulatory submissions. Disclaimer: this report is audit evidence — it does not constitute regulatory certification.",
      },
    ],
  },

  // ── Governance Principles ─────────────────────────────────────────────────
  {
    id: "governance-principles",
    category: "Governance",
    title: "AI Governance Principles",
    summary: "Transparency, Human Oversight, Accountability, Privacy by Design, Evidence-Based.",
    icon: Shield,
    content: [
      { heading: "Transparency", body: "All SARO scoring decisions are explainable via SHAP values. No black-box outputs. Audit trails are immutable and human-readable." },
      { heading: "Human Oversight", body: "No automated decisions. Every finding, remediation, and report requires human review and sign-off. SARO is an evidence tool, not an autonomous decision-maker." },
      { heading: "Accountability", body: "Every scan is tied to a user, tenant, and timestamp. TRACE records are immutable. Hash-chain integrity ensures non-repudiation for audit purposes." },
      { heading: "Privacy by Design", body: "SARO processes only prompt + raw_output text. No PII is stored beyond what is contained in the submitted text. Tenants control retention periods." },
      { heading: "Evidence-Based", body: "All claims are backed by verifiable TRACE records. SARO never makes assertions without a computable basis. Evidence packages are exportable for third-party review." },
    ],
  },
];

const CATEGORIES = ["All", ...Array.from(new Set(ARTICLES.map((a) => a.category)))];

export default function KnowledgePortal() {
  const [search,    setSearch]    = useState("");
  const [category,  setCategory]  = useState("All");
  const [expanded,  setExpanded]  = useState(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return ARTICLES.filter((a) => {
      const matchCat = category === "All" || a.category === category;
      const matchQ   = !q || a.title.toLowerCase().includes(q) || a.summary.toLowerCase().includes(q) ||
        a.content.some((s) => s.heading.toLowerCase().includes(q) || s.body.toLowerCase().includes(q));
      return matchCat && matchQ;
    });
  }, [search, category]);

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="Knowledge Portal"
        subtitle="SARO documentation, methodology, governance docs, and compliance reference"
      />

      <div style={{ padding: "var(--space-6)" }}>
        {/* Search + filter bar */}
        <div style={{ display: "flex", gap: 12, marginBottom: "var(--space-6)", flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ position: "relative", flex: 1, minWidth: 260, maxWidth: 500 }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--color-text-muted)" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search articles…"
              autoFocus
              style={{
                width: "100%", paddingLeft: 30, paddingRight: 12, paddingTop: 8, paddingBottom: 8,
                background: "var(--color-bg-surface)", border: "1px solid var(--color-border-default)",
                borderRadius: "var(--radius-md)", color: "var(--color-text-primary)",
                fontSize: "var(--text-sm)", fontFamily: "var(--font-body)", outline: "none",
                boxSizing: "border-box",
              }}
              onFocus={(e) => { e.target.style.borderColor = "var(--color-info)"; }}
              onBlur={(e) => { e.target.style.borderColor = "var(--color-border-default)"; }}
            />
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCategory(c)}
                style={{
                  padding: "5px 12px", borderRadius: 999, border: `1px solid ${category === c ? "var(--color-info)" : "var(--color-border-default)"}`,
                  background: category === c ? "var(--color-info-bg)" : "transparent",
                  color: category === c ? "var(--color-info)" : "var(--color-text-muted)",
                  cursor: "pointer", fontSize: "var(--text-xs)", fontFamily: "var(--font-display)",
                  fontWeight: "var(--weight-medium)",
                }}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px 0", color: "var(--color-text-muted)" }}>
            <BookOpen size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
            <div>No articles match your search.</div>
          </div>
        )}

        {/* Article cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 16 }}>
          {filtered.map((article) => {
            const Icon = article.icon;
            const isOpen = expanded === article.id;
            return (
              <div
                key={article.id}
                style={{
                  background: "var(--color-bg-surface)",
                  border: `1px solid ${isOpen ? "var(--color-info-border)" : "var(--color-border-subtle)"}`,
                  borderRadius: 8,
                  overflow: "hidden",
                  gridColumn: isOpen ? "1 / -1" : undefined,
                }}
              >
                {/* Card header */}
                <button
                  onClick={() => setExpanded(isOpen ? null : article.id)}
                  style={{
                    width: "100%", textAlign: "left", background: "none", border: "none",
                    padding: "var(--space-4) var(--space-5)", cursor: "pointer",
                    display: "flex", alignItems: "flex-start", gap: 12,
                  }}
                >
                  <div style={{
                    width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                    background: "var(--color-info-bg)", display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <Icon size={16} color="var(--color-info)" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-info)", fontWeight: "var(--weight-semibold)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>
                      {article.category}
                    </div>
                    <div style={{ fontSize: "var(--text-md)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)", marginBottom: 2 }}>
                      {article.title}
                    </div>
                    <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-muted)" }}>
                      {article.summary}
                    </div>
                  </div>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-info)", marginTop: 2, flexShrink: 0 }}>
                    {isOpen ? "Close ↑" : "Read →"}
                  </span>
                </button>

                {/* Expanded content */}
                {isOpen && (
                  <div style={{ borderTop: "1px solid var(--color-border-subtle)", padding: "var(--space-5)", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
                    {article.content.map((section, i) => (
                      <div key={i} style={{ background: "var(--color-bg-elevated)", borderRadius: 6, padding: "12px 14px" }}>
                        <div style={{ fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-primary)", marginBottom: 6 }}>
                          {section.heading}
                        </div>
                        <div style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", whiteSpace: "pre-line", lineHeight: 1.6 }}>
                          {section.body}
                        </div>
                        {section.link && (
                          <a
                            href={section.link.href}
                            target="_blank"
                            rel="noreferrer"
                            style={{ display: "inline-flex", alignItems: "center", gap: 4, marginTop: 8, fontSize: "var(--text-xs)", color: "var(--color-info)", textDecoration: "none" }}
                          >
                            <ExternalLink size={11} /> {section.link.label}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
