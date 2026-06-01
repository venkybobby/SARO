import { Check } from 'lucide-react'

const SARO_URL = 'https://saro-production-2993.up.railway.app/'

const plans = [
  {
    name: 'Starter',
    price: '$499',
    period: '/month',
    desc: 'For teams beginning their AI governance journey.',
    features: [
      'Up to 50k AI interactions/month',
      'Real-time risk scoring (0–100)',
      'TRACE audit timelines',
      'Prompt injection detection',
      'NIST AI RMF evidence support',
      '5 users',
      'Email support',
    ],
    cta: 'Get Started',
    highlight: false,
    accent: '#00d4ff',
  },
  {
    name: 'Pro',
    price: '$1,999',
    period: '/month',
    desc: 'For scaling enterprises with complex AI deployments.',
    features: [
      'Up to 500k AI interactions/month',
      'Everything in Starter',
      'Advanced threat protection suite',
      'Automated governance policies',
      'SOC 2 · ISO 27001 · GDPR evidence packs',
      'AI agent sandboxing',
      'Circuit-breaker orchestration',
      '20 users',
      'Priority support + SLA',
    ],
    cta: 'Get Started — Most Popular',
    highlight: true,
    accent: '#00ff9d',
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    desc: 'Unlimited governance for regulated industries.',
    features: [
      'Unlimited AI interactions',
      'Everything in Pro',
      'EU AI Act full compliance workflow',
      'ISO 42001 · AIGP · HIPAA evidence',
      'Dedicated compliance engineer',
      'Custom rule pack development',
      'On-prem / private cloud deployment',
      'Unlimited users',
      '24/7 dedicated support + SLA',
    ],
    cta: 'Contact Sales',
    highlight: false,
    accent: '#a78bfa',
  },
]

export default function Pricing() {
  return (
    <section id="pricing" className="py-24 px-4 sm:px-6">
      <div className="section-divider mb-24" />

      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00ff9d30] bg-[#00ff9d0a] text-[#00ff9d] text-sm font-medium mb-4">
            Pricing
          </div>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
            Governance at every
            <br />
            <span className="gradient-text">enterprise scale</span>
          </h2>
          <p className="text-slate-400 text-lg max-w-xl mx-auto">
            Start governing your AI in minutes. Scale as your deployment grows.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`relative card-hover rounded-2xl p-8 flex flex-col ${
                p.highlight
                  ? 'border-2 border-[#00ff9d40] bg-[#00ff9d05] shadow-[0_0_60px_rgba(0,255,157,0.1)]'
                  : 'border border-[#1a1a2e] bg-[#0f0f0f]'
              }`}
            >
              {p.highlight && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-[#00ff9d] text-[#0a0a0a] text-xs font-black tracking-wide">
                  MOST POPULAR
                </div>
              )}

              <div className="mb-6">
                <div className="text-sm font-bold mb-1" style={{ color: p.accent }}>
                  {p.name}
                </div>
                <div className="flex items-end gap-1 mb-2">
                  <span className="text-4xl font-extrabold text-white">{p.price}</span>
                  <span className="text-slate-400 text-sm pb-1">{p.period}</span>
                </div>
                <p className="text-slate-400 text-sm">{p.desc}</p>
              </div>

              <ul className="space-y-3 flex-1 mb-8">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-slate-300">
                    <Check className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: p.accent }} />
                    {f}
                  </li>
                ))}
              </ul>

              <a
                href={SARO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={`block text-center px-6 py-3 rounded-xl font-semibold text-sm transition-all ${
                  p.highlight
                    ? 'bg-[#00ff9d] text-[#0a0a0a] hover:opacity-90 shadow-lg hover:shadow-[0_0_30px_rgba(0,255,157,0.3)]'
                    : 'border border-[#1a1a2e] text-white hover:border-[#00d4ff40] hover:text-[#00d4ff]'
                }`}
              >
                {p.cta}
              </a>
            </div>
          ))}
        </div>

        <p className="text-center text-slate-600 text-xs mt-8">
          All plans include SOC 2 compliant infrastructure. No setup fees. Cancel anytime.
          Human review required before any regulatory submission.
        </p>
      </div>
    </section>
  )
}
