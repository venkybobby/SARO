/**
 * RiskDetail — full risk view with tabs: Details, Remediation, TRACE History.
 * Reached by clicking the eye icon on any row in RiskRegister.
 */
import React, { useEffect, useState } from "react";
import { ArrowLeft, Edit2, ExternalLink, AlertTriangle, CheckCircle, Clock, Sparkles } from "lucide-react";
import { Badge, Button, PageHeader, Skeleton } from "../components/ui/index.jsx";

const TABS = ["Details", "Remediation", "TRACE History"];

const SCORE_BANDS = [
  { max: 30,  label: "Low",      color: "#16a34a" },
  { max: 50,  label: "Medium",   color: "#ca8a04" },
  { max: 70,  label: "High",     color: "#ea580c" },
  { max: 101, label: "Critical", color: "#dc2626" },
];

export default function RiskDetail({ token, riskId, onNavigate, suggestedRemediation }) {
  const [risk,       setRisk]       = useState(null);
  const [traces,     setTraces]     = useState([]);
  const [remediation,setRemediation]= useState([]);
  const [loading,    setLoading]    = useState(true);
  // STORY-002 AC-2: arriving with a suggested remediation opens that tab directly.
  const [activeTab,  setActiveTab]  = useState(suggestedRemediation ? "Remediation" : "Details");

  useEffect(() => {
    if (!riskId) return;
    async function load() {
      setLoading(true);
      try {
        const rr = await fetch(`/api/v1/risks/${riskId}`, { headers: { Authorization: `Bearer ${token}` } });
        if (rr.ok) {
          const found = await rr.json();
          setRisk(found);

          // If the risk has an audit_id, also fetch its trace and remediation data
          const auditId = found?.audit_id;
          if (auditId) {
            const [tr, remr] = await Promise.allSettled([
              fetch(`/api/v1/traces/${auditId}`, { headers: { Authorization: `Bearer ${token}` } }),
              fetch(`/api/v1/remediation?audit_id=${auditId}`, { headers: { Authorization: `Bearer ${token}` } }),
            ]);
            if (tr.status === "fulfilled" && tr.value.ok) setTraces(await tr.value.json());
            if (remr.status === "fulfilled" && remr.value.ok) {
              const d = await remr.value.json();
              setRemediation(Array.isArray(d) ? d : d.items || []);
            }
          }
        } else {
          setRisk(null);
        }
      } catch {
        setRisk(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token, riskId]);

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        {[...Array(4)].map((_, i) => <Skeleton key={i} height={40} style={{ marginBottom: 12 }} />)}
      </div>
    );
  }

  if (!risk) {
    return (
      <div style={{ padding: 24 }}>
        <Button variant="ghost" size="sm" onClick={() => onNavigate?.("risk_register")}>
          <ArrowLeft size={14} /> Back to Register
        </Button>
        <div style={{ marginTop: 32, textAlign: "center", color: "var(--color-text-muted)", fontSize: 14 }}>
          Risk not found.
        </div>
      </div>
    );
  }

  const sevColor = { critical: "#dc2626", high: "#ea580c", medium: "#ca8a04", low: "#16a34a" }[risk.severity] || "#6b7280";

  return (
    <div style={{ background: "var(--color-bg-base)", minHeight: "100vh" }}>
      <PageHeader
        title={risk.title}
        subtitle={`${risk.id} · ${risk.category}`}
        breadcrumb={
          <>
            <span style={{ cursor: "pointer", color: "var(--color-info)" }} onClick={() => onNavigate?.("risk_register")}>
              Risk Register
            </span>
            <span style={{ color: "var(--color-text-muted)" }}> › </span>
            <span style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-block", verticalAlign: "bottom" }}>
              {risk.title}
            </span>
          </>
        }
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="ghost" size="sm" onClick={() => onNavigate?.("risk_register")}>
              <ArrowLeft size={14} /> Back
            </Button>
            <Button variant="secondary" size="sm" onClick={() => onNavigate?.("risk_form", riskId)}>
              <Edit2 size={13} /> Edit
            </Button>
            <Button variant="secondary" size="sm" onClick={() => onNavigate?.("ai_insights", riskId)}>
              <Sparkles size={13} /> View AI Insights
            </Button>
          </div>
        }
      />

      {/* Status bar */}
      <div style={{
        padding: "var(--space-4) var(--space-6)",
        borderBottom: "1px solid var(--color-border-subtle)",
        background: "var(--color-bg-surface)",
        display: "flex", alignItems: "center", gap: "var(--space-6)", flexWrap: "wrap",
      }}>
        <Badge severity={risk.severity} />
        <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)", marginRight: 4 }}>Status</span>
          {risk.status}
        </div>
        <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)", marginRight: 4 }}>Owner</span>
          {risk.owner || "—"}
        </div>
        <div style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)", marginRight: 4 }}>Due</span>
          <span style={{ color: risk.dueDate && new Date(risk.dueDate) < new Date() ? "var(--color-critical)" : "inherit" }}>
            {risk.dueDate || "—"}
          </span>
        </div>
        {risk.risk_score != null && (
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {SCORE_BANDS.map((band) => (
                <span key={band.label} style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, color: "var(--color-text-muted)" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: band.color, display: "inline-block" }} />
                  {band.label}
                </span>
              ))}
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 16, color: sevColor }}>
              {risk.risk_score}/100
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{
        padding: "0 var(--space-6)",
        borderBottom: "1px solid var(--color-border-subtle)",
        background: "var(--color-bg-surface)",
        display: "flex", gap: 0,
      }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            style={{
              padding: "var(--space-3) var(--space-5)",
              border: "none", background: "none", cursor: "pointer",
              fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
              color: activeTab === t ? "var(--color-info)" : "var(--color-text-muted)",
              borderBottom: activeTab === t ? "2px solid var(--color-info)" : "2px solid transparent",
              fontWeight: activeTab === t ? "var(--weight-semibold)" : "var(--weight-normal)",
              marginBottom: -1,
            }}
          >
            {t}
            {t === "Remediation" && (
              <span style={{ marginLeft: 6, background: remediation.length > 0 ? "var(--color-info-bg)" : "var(--color-bg-overlay)", color: remediation.length > 0 ? "var(--color-info)" : "var(--color-text-muted)", padding: "1px 6px", borderRadius: 999, fontSize: 11, fontWeight: 700 }}>
                {remediation.length}
              </span>
            )}
            {t === "TRACE History" && (
              <span style={{ marginLeft: 6, background: "var(--color-bg-overlay)", color: "var(--color-text-muted)", padding: "1px 6px", borderRadius: 999, fontSize: 11 }}>
                {traces.length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div style={{ padding: "var(--space-6)", maxWidth: 860 }}>

        {/* ── Details tab ── */}
        {activeTab === "Details" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
              {[
                { label: "Category",  value: risk.category },
                { label: "Severity",  value: <Badge severity={risk.severity} /> },
                { label: "Owner",     value: risk.owner || "—" },
                { label: "Due Date",  value: risk.dueDate || "—" },
                { label: "Status",    value: risk.status },
                { label: "Created",   value: risk.created_at ? new Date(risk.created_at).toLocaleDateString() : "—" },
              ].map(({ label, value }) => (
                <div key={label} style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 14, color: "var(--color-text-primary)" }}>{value}</div>
                </div>
              ))}
            </div>

            {risk.audit_id && (
              <div style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)", borderRadius: 8, padding: "12px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>Source Audit</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text-secondary)" }}>{risk.audit_id}</div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => onNavigate?.("trace_view", risk.audit_id)}>
                  <ExternalLink size={12} /> View TRACE
                </Button>
              </div>
            )}
          </div>
        )}

        {/* ── Remediation tab ── */}
        {activeTab === "Remediation" && (
          <div>
            {/* STORY-002 AC-2: remediation suggested by an AI insight is
                highlighted for the human reviewer to validate */}
            {suggestedRemediation && (
              <div
                data-testid="suggested-remediation"
                style={{
                  background: "var(--color-ai-bg)", border: "1px solid var(--color-ai-border)",
                  borderRadius: 8, padding: 16, marginBottom: 14,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <Sparkles size={14} style={{ color: "var(--color-ai)" }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-ai)" }}>
                    Suggested by SARO
                  </span>
                </div>
                <p style={{ fontSize: 13, color: "var(--color-text-primary)", margin: 0 }}>
                  {suggestedRemediation}
                </p>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6 }}>
                  Recommended remediation — human validation required
                </div>
              </div>
            )}
            {remediation.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "var(--color-text-muted)", fontSize: 14 }}>
                <CheckCircle size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
                <div>No remediation actions recorded for this risk.</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>Remediation actions are created automatically when a scan flags a finding.</div>
              </div>
            ) : (
              remediation.map((item, i) => (
                <div key={i} style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)", borderRadius: 8, padding: 16, marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                    <Badge severity={item.severity || "medium"} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)" }}>{item.title || item.description}</span>
                    <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-text-muted)" }}>{item.status}</span>
                  </div>
                  {item.description && item.title && (
                    <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: 0 }}>{item.description}</p>
                  )}
                  <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 6 }}>
                    Recommended remediation — human validation required
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── TRACE History tab ── */}
        {activeTab === "TRACE History" && (
          <div>
            {traces.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "var(--color-text-muted)", fontSize: 14 }}>
                <Clock size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
                <div>No TRACE records linked to this risk.</div>
                {risk.audit_id && (
                  <Button variant="secondary" size="sm" style={{ marginTop: 12 }} onClick={() => onNavigate?.("trace_view", risk.audit_id)}>
                    View source audit in TRACE →
                  </Button>
                )}
              </div>
            ) : (
              traces.map((t, i) => {
                const score = t.risk_score != null ? Math.round(t.risk_score <= 1 ? t.risk_score * 100 : t.risk_score) : null;
                const color = score >= 70 ? "#dc2626" : score >= 40 ? "#ca8a04" : "#16a34a";
                return (
                  <div key={i} style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)", borderRadius: 8, padding: "12px 16px", marginBottom: 8, display: "flex", alignItems: "center", gap: 16 }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text-muted)", flex: 1 }}>
                      Gate {t.gate_id} — {t.rule_id || "trace record"}
                    </div>
                    <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>{t.result}</span>
                    {score != null && <span style={{ fontWeight: 700, color, fontFamily: "var(--font-mono)" }}>{score}</span>}
                    <Button variant="ghost" size="sm" onClick={() => onNavigate?.("trace_view", risk.audit_id)}>
                      <ExternalLink size={12} />
                    </Button>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}
