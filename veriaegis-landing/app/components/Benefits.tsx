const stats = [
  { val: '99.9%', label: 'Threat Detection Rate', sub: 'Across all AI interaction types' },
  { val: '< 50ms', label: 'Scan Latency', sub: 'Real-time risk scoring' },
  { val: '80%', label: 'Faster Compliance', sub: 'vs. manual audit workflows' },
  { val: '100%', label: 'Audit Coverage', sub: 'Every interaction logged' },
  { val: 'Zero-trust', label: 'Governance Model', sub: 'No writes to client systems' },
  { val: '6 Frameworks', label: 'Compliance Coverage', sub: 'NIST · EU AI Act · ISO 42001 · AIGP · GDPR · HIPAA' },
]

export default function Benefits() {
  return (
    <section className="py-24 px-4 sm:px-6">
      <div className="section-divider mb-24" />

      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00d4ff30] bg-[#00d4ff0a] text-[#00d4ff] text-sm font-medium mb-4">
            Trusted by enterprises that refuse to take AI risks
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
            The numbers
            <br />
            <span className="gradient-text">speak for themselves</span>
          </h2>
        </div>

        {/* Stats grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {stats.map((s) => (
            <div
              key={s.val}
              className="card-hover rounded-2xl border border-[#1a1a2e] bg-[#0f0f0f] p-8 text-center"
            >
              <div className="text-3xl font-extrabold text-[#00d4ff] mb-2">{s.val}</div>
              <div className="text-white font-semibold text-sm mb-1">{s.label}</div>
              <div className="text-slate-500 text-xs">{s.sub}</div>
            </div>
          ))}
        </div>

        {/* Compliance badge row */}
        <div className="mt-16 text-center">
          <p className="text-slate-500 text-sm mb-6">Evidence support for frameworks including</p>
          <div className="flex flex-wrap justify-center gap-3">
            {['NIST AI RMF 1.0', 'EU AI Act', 'ISO 42001', 'AIGP', 'SOC 2', 'GDPR', 'HIPAA', 'ISO 27001'].map(
              (fw) => (
                <span
                  key={fw}
                  className="px-4 py-1.5 rounded-full border border-[#1a1a2e] bg-[#0f0f0f] text-slate-400 text-xs font-medium"
                >
                  {fw}
                </span>
              )
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
