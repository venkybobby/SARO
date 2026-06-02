import { Shield, ArrowRight } from 'lucide-react'

const SARO_URL = 'https://saro-production-2993.up.railway.app/'

export default function CTABanner() {
  return (
    <section className="py-24 px-4 sm:px-6">
      <div className="section-divider mb-24" />

      <div className="max-w-4xl mx-auto">
        <div className="relative rounded-3xl border border-[#00d4ff20] bg-gradient-to-br from-[#0f0f1a] via-[#0a0a0a] to-[#0f1a0f] p-12 text-center overflow-hidden">
          {/* Background glows */}
          <div className="absolute top-0 left-1/4 w-64 h-64 bg-[#00d4ff08] rounded-full blur-[80px] pointer-events-none" />
          <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-[#00ff9d06] rounded-full blur-[80px] pointer-events-none" />

          <div className="relative z-10">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#00d4ff] to-[#00ff9d] flex items-center justify-center shadow-[0_0_40px_rgba(0,212,255,0.4)]">
                <Shield className="w-8 h-8 text-[#0a0a0a]" strokeWidth={2.5} />
              </div>
            </div>

            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4">
              Ready to govern your AI?
            </h2>
            <p className="text-slate-400 text-lg max-w-xl mx-auto mb-10 leading-relaxed">
              Join enterprises deploying AI with confidence. Start your SARO governance journey
              today — no setup fees, no AI model access required.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href={SARO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-2 px-10 py-4 rounded-xl bg-gradient-to-r from-[#00d4ff] to-[#00ff9d] text-[#0a0a0a] font-bold text-base hover:opacity-90 transition-all shadow-xl hover:shadow-[0_0_50px_rgba(0,212,255,0.4)] hover:scale-105"
              >
                Sign In to SARO
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </a>
              <a
                href="mailto:hello@veriaegis.ai"
                className="px-10 py-4 rounded-xl border border-[#00d4ff30] text-[#00d4ff] font-semibold text-base hover:bg-[#00d4ff0f] transition-colors"
              >
                Talk to Sales
              </a>
            </div>

            <p className="mt-8 text-slate-600 text-xs">
              SARO provides audit evidence only. Human review required before any regulatory
              submission. &mdash; SARO v8.0.0
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
