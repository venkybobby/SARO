import React, { useState, useEffect } from "react";
import { X, Check, Clock, ChevronRight, Lightbulb, AlertCircle } from "lucide-react";
import { AIBadge, Badge, Button, EmptyState, PageHeader, Skeleton } from "../components/ui/index.jsx";

const MOCK_INSIGHTS = [
  {
    id: "INS-001",
    title: "Uncontrolled risk approaching escalation window",
    why: "Risk R-042 has been open for 47 days without a control assigned. Based on your industry sector (Financial Services), uncontrolled risks of this type typically escalate within 60 days. ISO 27001 Annex A.8.2 recommends assigning an owner within 30 days of identification.",
    confidence: 0.87,
    basis: "14 similar risks in your register",
    severity: "critical",
    riskId: "R-042",
    status: "active",
  },
  {
    id: "INS-002",
    title: "Model drift pattern matches prior incident",
    why: "The KS-test p-value for the fraud scoring model has dropped below 0.05 for 3 consecutive days. In Q3 2025, a similar pattern preceded a significant bias incident. Consider triggering a manual review before automated mitigation kicks in.",
    confidence: 0.72,
    basis: "TRACE records from Q3 2025 incident",
    severity: "high",
    riskId: "R-088",
    status: "active",
  },
  {
    id: "INS-003",
    title: "GDPR consent gap likely to affect 3 data subjects",
    why: "The onboarding flow introduced in v7.2 does not record granular consent categories as required by GDPR Art. 7. Based on traffic patterns, approximately 3 data subjects per day are being onboarded without complete consent records.",
    confidence: 0.61,
    basis: "Traffic analysis + framework mapping",
    severity: "medium",
    riskId: "R-033",
    status: "dismissed",
  },
];

function ConfidenceIndicator({ level }) {
  const pct = Math.round(level * 100);
  const color = level >= 0.8 ? "var(--color-low)" : level >= 0.6 ? "var(--color-medium)" : "var(--color-high)";
  const label = level >= 0.8 ? "High confidence" : level >= 0.6 ? "Medium confidence" : "Low confidence";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", gap: 3 }}>
        {[...Array(5)].map((_, i) => (
          <div key={i} style={{
            width: 16, height: 4, borderRadius: 2,
            background: i < Math.round(level * 5) ? color : "var(--color-bg-overlay)",
          }} />
        ))}
      </div>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
        {label} · {pct}%
      </span>
    </div>
  );
}

function AIThinkingState({ message, steps }) {
  return (
    <div style={{
      background: "var(--color-ai-bg)", border: "1px solid var(--color-ai-border)",
      borderRadius: "var(--radius-lg)", padding: "var(--space-6)",
      display: "flex", flexDirection: "column", gap: "var(--space-4)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <span style={{ color: "var(--color-ai)", animation: "spin 1.2s linear infinite", display: "inline-block" }}>
          <Lightbulb size={18} />
        </span>
        <span style={{ fontSize: "var(--text-sm)", color: "var(--color-ai)", fontWeight: "var(--weight-medium)", fontFamily: "var(--font-display)" }}>
          {message}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {steps.map((step, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--text-sm)" }}>
            {step.done ? (
              <Check size={14} color="var(--color-low)" />
            ) : (
              <span style={{
                width: 14, height: 14, border: "2px solid var(--color-ai)",
                borderTopColor: "transparent", borderRadius: "50%",
                animation: "spin 0.7s linear infinite", display: "inline-block", flexShrink: 0,
              }} />
            )}
            <span style={{ color: step.done ? "var(--color-text-muted)" : "var(--color-text-primary)" }}>
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function InsightCard({ insight, onAccept, onSnooze, onDismiss }) {
  return (
    <div style={{
      background: "var(--color-bg-surface)",
      border: "1px solid var(--color-border-default)",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-3)",
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)", flexWrap: "wrap" }}>
            <Badge severity={insight.severity} />
            <AIBadge />
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-text-muted)" }}>
              {insight.riskId}
            </span>
          </div>
          <h3 style={{
            fontSize: "var(--text-base)", fontWeight: "var(--weight-semibold)",
            color: "var(--color-text-primary)", fontFamily: "var(--font-display)",
          }}>
            {insight.title}
          </h3>
        </div>
      </div>

      {/* Confidence */}
      <div style={{ padding: "var(--space-3) var(--space-5)", borderBottom: "1px solid var(--color-border-subtle)" }}>
        <ConfidenceIndicator level={insight.confidence} />
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-muted)", marginTop: "var(--space-1)" }}>
          Based on {insight.basis}
        </p>
      </div>

      {/* Explanation */}
      <div style={{ padding: "var(--space-4) var(--space-5)", borderBottom: "1px solid var(--color-border-subtle)" }}>
        <p style={{ fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Why SARO flagged this
        </p>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
          {insight.why}
        </p>
      </div>

      {/* Actions */}
      <div style={{
        padding: "var(--space-3) var(--space-5)",
        display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap",
      }}>
        <Button variant="primary" size="sm" onClick={() => onAccept(insight.id)}>
          <Check size={13} /> Apply suggestion
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onSnooze(insight.id)}>
          <Clock size={13} /> Remind later
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDismiss(insight.id)}>
          <X size={13} /> Dismiss
        </Button>
        <a href="#" style={{
          marginLeft: "auto", fontSize: "var(--text-xs)", color: "var(--color-info)",
          display: "flex", alignItems: "center", gap: 4,
        }}>
          View framework reference <ChevronRight size={11} />
        </a>
      </div>
    </div>
  );
}

export default function AIInsights({ token }) {
  const [aiLoading, setAiLoading]   = useState(true);
  const [insights,  setInsights]    = useState(MOCK_INSIGHTS);
  const [filter,    setFilter]      = useState("active");

  const STEPS = [
    { label: "Reading risk patterns",             done: true },
    { label: "Comparing against frameworks",      done: true },
    { label: "Generating recommendations",        done: false },
  ];

  useEffect(() => {
    const t = setTimeout(() => setAiLoading(false), 2200);
    return () => clearTimeout(t);
  }, []);

  const visible = insights.filter((i) => i.status === filter);

  function handleDismiss(id) {
    setInsights((prev) => prev.map((i) => i.id === id ? { ...i, status: "dismissed" } : i));
  }
  function handleAccept(id) {
    setInsights((prev) => prev.map((i) => i.id === id ? { ...i, status: "accepted" } : i));
  }
  function handleSnooze(id) {
    setInsights((prev) => prev.map((i) => i.id === id ? { ...i, status: "snoozed" } : i));
  }

  const TAB_COUNTS = {
    active:    insights.filter((i) => i.status === "active").length,
    accepted:  insights.filter((i) => i.status === "accepted").length,
    snoozed:   insights.filter((i) => i.status === "snoozed").length,
    dismissed: insights.filter((i) => i.status === "dismissed").length,
  };

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="AI Insights"
        subtitle="SARO-generated risk recommendations — human review required"
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>AI Insights</span></>}
      />

      {/* Filter tabs */}
      <div style={{
        padding: "0 var(--space-6)",
        background: "var(--color-bg-surface)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", gap: "var(--space-1)",
      }}>
        {Object.entries(TAB_COUNTS).map(([key, count]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: "none", border: "none",
              borderBottom: `2px solid ${filter === key ? "var(--color-info)" : "transparent"}`,
              color: filter === key ? "var(--color-info)" : "var(--color-text-muted)",
              fontSize: "var(--text-sm)", cursor: "pointer",
              fontFamily: "var(--font-display)", fontWeight: "var(--weight-medium)",
              textTransform: "capitalize",
              transition: "color var(--transition-fast)",
            }}
          >
            {key} ({count})
          </button>
        ))}
      </div>

      <div style={{ padding: "var(--space-6)" }}>
        {aiLoading ? (
          <AIThinkingState message="Analyzing your risk register…" steps={STEPS} />
        ) : visible.length === 0 ? (
          <EmptyState
            icon={<AlertCircle />}
            title={filter === "active" ? "No active insights" : `No ${filter} insights`}
            description={filter === "active" ? "SARO has no new recommendations. Check back after adding more risks." : `No insights in this state.`}
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {visible.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                onAccept={handleAccept}
                onSnooze={handleSnooze}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
