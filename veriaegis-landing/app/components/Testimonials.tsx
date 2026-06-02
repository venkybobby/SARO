const testimonials = [
  {
    quote:
      'SARO transformed our AI governance posture overnight. What used to take our compliance team three weeks now takes three hours — with better coverage and a full audit trail.',
    name: 'Chief Risk Officer',
    company: 'Global Financial Services Group',
    initials: 'GF',
    color: '#00d4ff',
  },
  {
    quote:
      'We were deploying LLM agents across 12 product lines with zero visibility. SARO gave us real-time orchestration and the confidence to scale AI safely under EU AI Act obligations.',
    name: 'VP of AI Engineering',
    company: 'European Insurance Leader',
    initials: 'EI',
    color: '#00ff9d',
  },
  {
    quote:
      'The prompt injection detection alone saved us from a significant data breach during a red-team exercise. SARO caught what our existing security stack completely missed.',
    name: 'CISO',
    company: 'Fortune 500 Healthcare Provider',
    initials: 'HC',
    color: '#a78bfa',
  },
  {
    quote:
      'SARO\'s TRACE timeline is now the single source of truth for every AI decision we make. Our board and regulators both asked for it by name at our last audit review.',
    name: 'Chief Compliance Officer',
    company: 'Tier 1 Investment Bank',
    initials: 'IB',
    color: '#fbbf24',
  },
]

export default function Testimonials() {
  return (
    <section className="py-24 px-4 sm:px-6">
      <div className="section-divider mb-24" />

      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#a78bfa30] bg-[#a78bfa0a] text-[#a78bfa] text-sm font-medium mb-4">
            Enterprise Voices
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
            Trusted by the teams
            <br />
            <span className="gradient-text">who can&apos;t afford to get AI wrong</span>
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 gap-6">
          {testimonials.map((t) => (
            <div
              key={t.name}
              className="card-hover rounded-2xl border border-[#1a1a2e] bg-[#0f0f0f] p-8"
            >
              {/* Quote mark */}
              <div className="text-4xl font-serif leading-none mb-4" style={{ color: t.color }}>
                &ldquo;
              </div>
              <p className="text-slate-300 text-sm leading-relaxed mb-6 italic">{t.quote}</p>

              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold text-[#0a0a0a]"
                  style={{ background: t.color }}
                >
                  {t.initials}
                </div>
                <div>
                  <div className="text-white text-sm font-semibold">{t.name}</div>
                  <div className="text-slate-500 text-xs">{t.company}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
