import { AlertTriangle, Zap, Lock } from 'lucide-react'

const problems = [
  {
    icon: AlertTriangle,
    color: '#ff6b6b',
    title: 'Uncontrolled AI Proliferation',
    desc: 'Teams deploy AI models and agents without visibility, version control, or behaviour monitoring — creating invisible risk vectors across your enterprise stack.',
  },
  {
    icon: Zap,
    color: '#ffd93d',
    title: 'Sophisticated AI Threats',
    desc: 'Prompt injection, jailbreaking, data exfiltration, and hallucination attacks exploit unguarded AI models — bypassing traditional security controls entirely.',
  },
  {
    icon: Lock,
    color: '#00d4ff',
    title: 'Compliance Blind Spots',
    desc: 'EU AI Act, NIST AI RMF, SOC 2, GDPR, and HIPAA impose rigorous obligations on AI systems — but manual audits can\'t keep pace with AI deployment velocity.',
  },
]

export default function Problem() {
  return (
    <section id="features" className="py-24 px-4 sm:px-6 relative overflow-hidden">
      <div className="section-divider mb-24" />

      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#ff6b6b30] bg-[#ff6b6b0a] text-[#ff6b6b] text-sm font-medium mb-4">
            The Problem
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
            AI is moving fast.
            <br />
            <span className="gradient-text">Your governance can&apos;t afford to lag.</span>
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            Every unmonitored AI interaction is a potential compliance failure, security breach,
            or reputational risk. The cost of inaction compounds daily.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {problems.map((p) => (
            <div
              key={p.title}
              className="card-hover rounded-2xl border border-[#1a1a2e] bg-[#0f0f0f] p-8"
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                style={{ background: `${p.color}15` }}
              >
                <p.icon className="w-6 h-6" style={{ color: p.color }} />
              </div>
              <h3 className="text-lg font-bold text-white mb-3">{p.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
