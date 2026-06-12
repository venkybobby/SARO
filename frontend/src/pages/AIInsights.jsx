/**
 * AI Insights — SARO-generated risk recommendations, wired to the backend
 * insights API (SARO_AIInsights_Stories STORY-001…006).
 *
 * Compliance posture: every suggestion is advisory. The human-validation
 * disclaimer uses the exact wording from COMPLIANCE_CLAIMS_MATRIX.md and is
 * never de-emphasized, regardless of confidence score.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { X, Check, Clock, ChevronRight, Info, AlertCircle, AlertTriangle, Loader } from "lucide-react";
import { AIBadge, Badge, Button, ConfirmDialog, EmptyState, PageHeader } from "../components/ui/index.jsx";
import { fetchInsights, postInsightAction } from "../api/insightsService";
import { getFrameworkTarget } from "../utils/frameworkLinks";

// Exact wording from COMPLIANCE_CLAIMS_MATRIX.md — do not paraphrase.
export const DISCLAIMER_TEXT = "Recommended remediation — human validation required";
export const NO_REMEDIATION_TEXT = "Human review required: no automated remediation available";
const DISCLAIMER_WHY =
  "SARO recommendations support risk assessment but require compliance review before deployment.";

const FILTER_TABS = ["active", "accepted", "snoozed", "dismissed"];

// STORY-003 NFR: preserve scroll position when returning from a framework
// reference. Module-scoped because the page unmounts on navigation.
let savedScrollTop = null;

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

/**
 * STORY-004: compliance disclaimer shown near the action buttons of every
 * card. Warning-toned (never success-green), equally prominent at any
 * confidence level, with an accessible "why" explainer.
 */
function HumanReviewDisclaimer({ hasRemediation }) {
  const [showWhy, setShowWhy] = useState(false);
  return (
    <div data-testid="human-review-disclaimer" style={{ padding: "var(--space-2) var(--space-5)" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: "var(--space-2)",
        fontSize: "var(--text-xs)", color: "var(--color-medium)",
        fontWeight: "var(--weight-medium)",
      }}>
        <AlertTriangle size={12} aria-hidden="true" />
        <span role="note">{hasRemediation ? DISCLAIMER_TEXT : NO_REMEDIATION_TEXT}</span>
        <button
          type="button"
          aria-label="Why is human review required?"
          aria-expanded={showWhy}
          onClick={() => setShowWhy((s) => !s)}
          title={DISCLAIMER_WHY}
          style={{
            background: "none", border: "none", cursor: "pointer", padding: 2,
            color: "var(--color-text-muted)", display: "inline-flex", alignItems: "center",
          }}
        >
          <Info size={12} />
        </button>
      </div>
      {showWhy && (
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-text-secondary)", marginTop: "var(--space-1)" }}>
          {DISCLAIMER_WHY}
        </p>
      )}
    </div>
  );
}

function FrameworkReferenceLink({ insight, onViewFramework }) {
  if (!insight.framework) return null; // STORY-003 AC-3: nothing to reference → hidden
  const target = getFrameworkTarget(insight.framework);
  if (!target) {
    return (
      <span
        aria-disabled="true"
        title="No framework reference is available for this insight"
        style={{
          marginLeft: "auto", fontSize: "var(--text-xs)",
          color: "var(--color-text-muted)", cursor: "not-allowed",
        }}
      >
        Framework reference unavailable
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onViewFramework(insight, target)}
      style={{
        marginLeft: "auto", fontSize: "var(--text-xs)", color: "var(--color-info)",
        display: "flex", alignItems: "center", gap: 4,
        background: "none", border: "none", cursor: "pointer", padding: 0,
      }}
    >
      {target.label} <ChevronRight size={11} />
    </button>
  );
}

function InsightCard({ insight, readOnly, onApplyRequest, onSnooze, onDismiss, onViewFramework }) {
  const remediationSummary = insight.remediation_guidance
    ? insight.remediation_guidance.slice(0, 80)
    : "manual remediation";
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
              {insight.risk_id}
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
          {insight.description}
        </p>
        {insight.remediation_guidance && (
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)", lineHeight: 1.6, marginTop: "var(--space-2)" }}>
            <strong style={{ color: "var(--color-text-primary)" }}>Suggested remediation:</strong>{" "}
            {insight.remediation_guidance}
          </p>
        )}
      </div>

      {/* STORY-004 AC-1: disclaimer near the action buttons, always visible */}
      <HumanReviewDisclaimer hasRemediation={Boolean(insight.remediation_guidance)} />

      {/* Actions */}
      <div style={{
        padding: "var(--space-3) var(--space-5)",
        display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap",
      }}>
        <Button
          variant="primary"
          size="sm"
          disabled={readOnly}
          ariaLabel={`Apply suggestion: ${remediationSummary}`}
          onClick={() => onApplyRequest(insight)}
        >
          <Check size={13} /> Apply suggestion
        </Button>
        <Button variant="ghost" size="sm" disabled={readOnly} onClick={() => onSnooze(insight)}>
          <Clock size={13} /> Remind later
        </Button>
        <Button variant="ghost" size="sm" disabled={readOnly} onClick={() => onDismiss(insight)}>
          <X size={13} /> Dismiss
        </Button>
        <FrameworkReferenceLink insight={insight} onViewFramework={onViewFramework} />
      </div>
    </div>
  );
}

export default function AIInsights({ token, user, toast, onNavigate, initialRiskId }) {
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true); // STORY-005 AC-1: true from the first render
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("active");
  const [riskFilter, setRiskFilter] = useState(initialRiskId || null);
  const [confirmTarget, setConfirmTarget] = useState(null);
  const abortRef = useRef(null);

  // Read-only personas may review insights but never act on them (STORY-004 edge).
  const readOnly = (user?.persona_role || user?.role) === "ai_auditor";

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const { insights: data } = await fetchInsights(token, {
        riskId: riskFilter || undefined,
        signal: controller.signal,
      });
      setInsights(data);
    } catch (err) {
      if (controller.signal.aborted && !err.timedOut) return; // unmount / refetch cancel
      setError(err);
    } finally {
      if (!controller.signal.aborted || abortRef.current === controller) {
        setLoading(false); // STORY-005 AC-2/AC-5: cleared the moment the fetch settles
      }
    }
  }, [token, riskFilter]);

  // STORY-001 AC-1/AC-4: fetch on every mount — no stale cache.
  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  // STORY-003 NFR: restore scroll position after returning from a framework
  // reference — must run after the cards have rendered, not inside load().
  useEffect(() => {
    if (loading || savedScrollTop == null) return;
    const main = document.getElementById("main-content");
    if (main) main.scrollTop = savedScrollTop;
    savedScrollTop = null;
  }, [loading, insights]);

  async function recordAction(insight, action, { confirmHumanReview = false } = {}) {
    try {
      await postInsightAction(token, insight.id, action, { confirmHumanReview });
      setInsights((prev) => prev.map((i) => (i.id === insight.id ? { ...i, status: action } : i)));
      return true;
    } catch (err) {
      if (err.status === 404) {
        toast?.error?.(`${insight.risk_id} no longer exists — the suggestion cannot be applied.`);
        setInsights((prev) => prev.filter((i) => i.id !== insight.id));
      } else if (err.status === 403) {
        toast?.error?.(err.detail || "Access denied: you do not have permission to modify this risk.");
      } else {
        toast?.error?.("Could not update the insight — please retry.");
      }
      return false;
    }
  }

  // STORY-002: Apply = confirm (restating human review) → record → navigate.
  async function handleApplyConfirmed() {
    const insight = confirmTarget;
    setConfirmTarget(null);
    const ok = await recordAction(insight, "accepted", { confirmHumanReview: true });
    if (!ok) return;
    toast?.success?.(`Remediation applied to ${insight.risk_id} — human validation required before deployment.`);
    onNavigate?.("risk_detail", {
      riskId: insight.risk_id,
      suggestedRemediation: insight.remediation_guidance,
      insightId: insight.id,
    });
  }

  function handleViewFramework(insight, target) {
    // NFR: log framework reference clicks (user, insight, framework, time).
    // User is identified by id, not email — PII minimization.
    console.info(
      `ai-insights.framework-click user=${user?.id || "unknown"} insight=${insight.id} framework=${insight.framework} at=${new Date().toISOString()}`
    );
    savedScrollTop = document.getElementById("main-content")?.scrollTop ?? null;
    onNavigate?.(target.page, { section: target.section });
  }

  const visible = insights.filter((i) => i.status === filter && (!riskFilter || i.risk_id === riskFilter));

  const TAB_COUNTS = Object.fromEntries(
    FILTER_TABS.map((key) => [key, insights.filter((i) => i.status === key).length])
  );
  const allEmpty = insights.length === 0;

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title="AI Insights"
        subtitle="SARO-generated risk recommendations — human review required"
        breadcrumb={<><span>Dashboard</span><span style={{ color: "var(--color-text-muted)" }}> › </span><span>AI Insights</span></>}
      />

      {riskFilter && (
        <div style={{
          padding: "var(--space-2) var(--space-6)",
          background: "var(--color-info-bg)", border: "1px solid var(--color-info-border)",
          display: "flex", alignItems: "center", gap: "var(--space-3)",
          fontSize: "var(--text-sm)", color: "var(--color-info)",
        }}>
          <span>Showing insights for <strong style={{ fontFamily: "var(--font-mono)" }}>{riskFilter}</strong></span>
          <Button variant="ghost" size="sm" onClick={() => setRiskFilter(null)}>Show all insights</Button>
        </div>
      )}

      {/* Filter tabs — STORY-006: zero-count tabs are de-emphasized (color +
          aria-label + tooltip, never opacity alone) unless everything is empty */}
      <div style={{
        padding: "0 var(--space-6)",
        background: "var(--color-bg-surface)",
        borderBottom: "1px solid var(--color-border-subtle)",
        display: "flex", gap: "var(--space-1)",
      }}>
        {FILTER_TABS.map((key) => {
          const count = TAB_COUNTS[key];
          const isSelected = filter === key;
          const deEmphasized = !allEmpty && count === 0 && !isSelected;
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              aria-current={isSelected ? "page" : undefined}
              aria-label={deEmphasized ? `${key} (0) — no items in this category` : `${key} (${count})`}
              title={deEmphasized ? "No items in this category" : undefined}
              style={{
                padding: "var(--space-3) var(--space-4)",
                minHeight: 44, // mobile touch target, kept even when de-emphasized
                background: "none", border: "none",
                borderBottom: `2px solid ${isSelected ? "var(--color-info)" : "transparent"}`,
                color: isSelected
                  ? "var(--color-info)"
                  : deEmphasized
                    ? "var(--color-text-muted)"
                    : "var(--color-text-secondary)",
                opacity: deEmphasized ? 0.55 : 1,
                fontSize: "var(--text-sm)", cursor: "pointer",
                fontFamily: "var(--font-display)",
                fontWeight: !deEmphasized && count > 0 ? "var(--weight-semibold)" : "var(--weight-medium)",
                textTransform: "capitalize",
                transition: "color var(--transition-fast), opacity var(--transition-fast)",
              }}
            >
              {key} ({count})
            </button>
          );
        })}
      </div>

      <div style={{ padding: "var(--space-6)" }}>
        {loading ? (
          // STORY-005: honest loading — bound to the fetch lifecycle, labelled
          // as data loading (not "AI reasoning").
          <div
            role="status"
            aria-live="polite"
            style={{
              background: "var(--color-ai-bg)", border: "1px solid var(--color-ai-border)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-6)",
              display: "flex", alignItems: "center", gap: "var(--space-3)",
            }}
          >
            <span style={{ color: "var(--color-ai)", animation: "spin 1.2s linear infinite", display: "inline-flex" }}>
              <Loader size={18} />
            </span>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--color-ai)", fontWeight: "var(--weight-medium)", fontFamily: "var(--font-display)" }}>
              Fetching insights…
            </span>
          </div>
        ) : error ? (
          // STORY-001 AC-3: error state with retry — mock data is never shown.
          <div
            role="alert"
            style={{
              background: "var(--color-bg-surface)", border: "1px solid var(--color-high)",
              borderRadius: "var(--radius-lg)", padding: "var(--space-6)",
              display: "flex", flexDirection: "column", gap: "var(--space-3)", alignItems: "flex-start",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", color: "var(--color-high)" }}>
              <AlertCircle size={16} />
              <strong style={{ fontSize: "var(--text-sm)" }}>
                {error.timedOut ? "The insights request timed out." : "Could not load insights."}
              </strong>
            </div>
            <p style={{ fontSize: "var(--text-sm)", color: "var(--color-text-secondary)" }}>
              {error.timedOut
                ? "The server did not respond within 10 seconds. Your data is unchanged — try again."
                : "The insights service returned an error. No cached or sample data is shown in its place."}
            </p>
            <Button variant="secondary" size="sm" onClick={load}>Retry</Button>
          </div>
        ) : visible.length === 0 ? (
          <EmptyState
            icon={<AlertCircle />}
            title={filter === "active" ? "No active insights" : `No ${filter} insights`}
            description={
              riskFilter
                ? `No ${filter} insights for ${riskFilter}.`
                : filter === "active"
                  ? "SARO has no new recommendations. Check back after adding more risks."
                  : `No insights in this state.`
            }
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {visible.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                readOnly={readOnly}
                onApplyRequest={setConfirmTarget}
                onSnooze={(i) => recordAction(i, "snoozed")}
                onDismiss={(i) => recordAction(i, "dismissed")}
                onViewFramework={handleViewFramework}
              />
            ))}
          </div>
        )}
      </div>

      {/* STORY-004 AC-3: applying restates the human-review requirement */}
      <ConfirmDialog
        open={confirmTarget !== null}
        title="Apply suggestion?"
        description={
          confirmTarget
            ? `${DISCLAIMER_TEXT}. Applying records your decision in the audit trail and opens ${confirmTarget.risk_id} so a human reviewer can validate the remediation before deployment.`
            : ""
        }
        confirmLabel="Apply — I will validate"
        cancelLabel="Cancel"
        onConfirm={handleApplyConfirmed}
        onCancel={() => setConfirmTarget(null)}
      />
    </div>
  );
}
