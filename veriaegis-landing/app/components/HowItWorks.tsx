const steps = [
  {
    num: '01',
    title: 'Connect Your AI Stack',
    desc: 'Integrate SARO with your models, agents, and pipelines via REST API. Zero-trust, read-only posture — no writes to your systems.',
    accent: '#00d4ff',
  },
  {
    num: '02',
    title: 'SARO Scans & Scores',
    desc: 'Every prompt and output is scored in real-time (0–100 risk scale). SHAP-explainable AI shows exactly why each risk flag was raised.',
    accent: '#00ff9d',
  },
  {
    num: '03',
    title: 'Real-time Orchestration & Blocking',
    desc: 'Automated circuit-breakers and policy rules act instantly on high-risk outputs. Human-in-the-loop workflows ensure critical decisions stay with your team.',
    accent: '#a78bfa',
  },
  {
    num: '04',
    title: 'Governance Reports & Audit Logs',
    desc: 'Immutable TRACE timelines and compliance evidence packages generated automatically for every scan — ready for auditors and regulators.',
    accent: '#fbbf24',
  },
]

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 px-4 sm:px-6 relative">
      <div className="section-divider mb-24" />

      {/* Background glow */}
      <div className="absolute top-1/2 left-0 w-64 h-64 bg-[#00d4ff05] rounded-full blur-[80px] pointer-events-none" />

      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00ff9d30] bg-[#00ff9d0a] text-[#00ff9d] text-sm font-medium mb-4">
            How It Works
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
            Enterprise AI governance
            <br />
            <span className="gradient-text">in four steps</span>
          </h2>
        </div>

        <div className="relative">
          {/* Vertical timeline line */}
          <div className="absolute left-8 sm:left-[calc(50%-1px)] top-0 bottom-0 w-px bg-gradient-to-b from-[#00d4ff30] via-[#00ff9d30] to-transparent hidden sm:block" />

          <div className="space-y-12">
            {steps.map((s, i) => (
              <div
                key={s.num}
                className={`relative flex flex-col sm:flex-row items-start gap-6 sm:gap-12 ${
                  i % 2 === 1 ? 'sm:flex-row-reverse' : ''
                }`}
              >
                {/* Content card */}
                <div className="flex-1 card-hover rounded-2xl border border-[#1a1a2e] bg-[#0f0f0f] p-7">
                  <div
                    className="text-xs font-black tracking-widest mb-2"
                    style={{ color: s.accent }}
                  >
                    STEP {s.num}
                  </div>
                  <h3 className="text-xl font-bold text-white mb-3">{s.title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">{s.desc}</p>
                </div>

                {/* Timeline node */}
                <div
                  className="hidden sm:flex items-center justify-center w-14 h-14 rounded-full border-2 flex-shrink-0 text-lg font-black z-10"
                  style={{
                    borderColor: s.accent,
                    color: s.accent,
                    background: `${s.accent}10`,
                    boxShadow: `0 0 20px ${s.accent}30`,
                  }}
                >
                  {s.num}
                </div>

                {/* Spacer for alternating layout */}
                <div className="flex-1 hidden sm:block" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
