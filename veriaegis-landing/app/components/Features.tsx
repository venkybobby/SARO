import {
  Activity, ShieldAlert, ClipboardCheck,
  FileText, Search, Box
} from 'lucide-react'

const features = [
  {
    icon: Activity,
    title: 'Real-time Risk Monitoring & Intelligent Orchestration',
    desc: 'Continuous scanning of every AI prompt and output. Dynamic risk scoring (0–100) with TRACE timeline audit trails for every interaction across your entire AI fleet.',
    accent: '#00d4ff',
  },
  {
    icon: ShieldAlert,
    title: 'Advanced Threat Protection',
    desc: 'Multi-layer detection of prompt injection, jailbreaking, data exfiltration, PII leakage, and adversarial attacks — before they reach production.',
    accent: '#ff6b6b',
  },
  {
    icon: ClipboardCheck,
    title: 'Automated Governance & Policy Enforcement',
    desc: 'Define, deploy, and enforce AI policies across all systems. Automated rule packs aligned to NIST AI RMF, EU AI Act, ISO 42001, and custom enterprise policies.',
    accent: '#00ff9d',
  },
  {
    icon: FileText,
    title: 'Compliance Automation & Reporting',
    desc: 'Auto-generate evidence packages for SOC 2, ISO 27001, GDPR, HIPAA, and EU AI Act. Audit-ready reports in minutes, not months.',
    accent: '#a78bfa',
  },
  {
    icon: Search,
    title: 'Full Audit Trails & Forensic Visibility',
    desc: 'SHA-256 hash-chained immutable TRACE records. Full forensic visibility into every AI decision — who, what, when, and why — for human auditor review.',
    accent: '#fbbf24',
  },
  {
    icon: Box,
    title: 'AI Agent Sandboxing & Behavior Control',
    desc: 'Isolate, monitor, and control autonomous AI agents. Circuit-breaker architecture automatically blocks anomalous behaviour before it causes damage.',
    accent: '#34d399',
  },
]

export default function Features() {
  return (
    <section id="capabilities" className="py-24 px-4 sm:px-6">
      <div className="section-divider mb-24" />
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00d4ff30] bg-[#00d4ff0a] text-[#00d4ff] text-sm font-medium mb-4">
            SARO Key Features
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
            Six pillars of
            <br />
            <span className="gradient-text">enterprise AI governance</span>
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            SARO orchestrates every layer of AI risk — from raw model outputs to boardroom
            compliance reports.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="card-hover group rounded-2xl border border-[#1a1a2e] bg-[#0f0f0f] p-7"
            >
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center mb-5 transition-transform group-hover:scale-110"
                style={{ background: `${f.accent}12` }}
              >
                <f.icon className="w-5 h-5" style={{ color: f.accent }} />
              </div>
              <h3 className="text-sm font-bold text-white mb-2 leading-tight">{f.title}</h3>
              <p className="text-slate-400 text-xs leading-relaxed">{f.desc}</p>
              <div
                className="mt-5 h-0.5 rounded-full transition-all duration-300 group-hover:w-full w-8"
                style={{ background: f.accent, opacity: 0.4 }}
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
