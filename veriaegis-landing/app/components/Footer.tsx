'use client'

import { useState } from 'react'
import { Shield, Send } from 'lucide-react'

const SARO_URL = 'https://saro-production-2993.up.railway.app/'

export default function Footer() {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    /* In production: POST to /api/contact */
    setSubmitted(true)
    setEmail(''); setName(''); setMessage('')
  }

  return (
    <footer className="border-t border-[#1a1a2e] bg-[#0a0a0a]">
      <div className="section-divider" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
        <div className="grid md:grid-cols-2 gap-16 mb-16">
          {/* Brand + links */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#00ff9d] flex items-center justify-center">
                <Shield className="w-4 h-4 text-[#0a0a0a]" strokeWidth={2.5} />
              </div>
              <span className="font-bold text-white text-lg">SARO by Veriaegis</span>
            </div>
            <p className="text-slate-500 text-sm leading-relaxed mb-6 max-w-xs">
              Smart AI Risk Orchestrator — Enterprise Governance Platform. Orchestrate, govern, and
              protect AI at enterprise scale.
            </p>

            <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              {[
                { label: 'Product', href: '#features' },
                { label: 'Features', href: '#capabilities' },
                { label: 'How It Works', href: '#how-it-works' },
                { label: 'Pricing', href: '#pricing' },
                { label: 'FAQ', href: '#faq' },
                { label: 'Sign In to SARO', href: SARO_URL },
                { label: 'Privacy Policy', href: '#' },
                { label: 'Terms of Service', href: '#' },
              ].map((l) => (
                <a
                  key={l.label}
                  href={l.href}
                  target={l.href.startsWith('http') ? '_blank' : undefined}
                  rel={l.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                  className="text-slate-500 hover:text-[#00d4ff] transition-colors py-1"
                >
                  {l.label}
                </a>
              ))}
            </div>
          </div>

          {/* Contact form */}
          <div>
            <h3 className="text-white font-bold text-lg mb-6">Get in touch</h3>
            {submitted ? (
              <div className="rounded-xl border border-[#00ff9d30] bg-[#00ff9d0a] p-6 text-center">
                <div className="text-[#00ff9d] font-semibold mb-1">Message received!</div>
                <p className="text-slate-400 text-sm">Our team will be in touch within 24 hours.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid sm:grid-cols-2 gap-4">
                  <input
                    type="text"
                    placeholder="Your name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-[#1a1a2e] bg-[#111] text-white text-sm placeholder-slate-600 focus:outline-none focus:border-[#00d4ff40]"
                  />
                  <input
                    type="email"
                    placeholder="Work email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-4 py-2.5 rounded-lg border border-[#1a1a2e] bg-[#111] text-white text-sm placeholder-slate-600 focus:outline-none focus:border-[#00d4ff40]"
                  />
                </div>
                <textarea
                  placeholder="How can SARO help your organisation?"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  required
                  rows={4}
                  className="w-full px-4 py-2.5 rounded-lg border border-[#1a1a2e] bg-[#111] text-white text-sm placeholder-slate-600 focus:outline-none focus:border-[#00d4ff40] resize-none"
                />
                <p className="text-slate-600 text-xs">
                  Protected by reCAPTCHA · Privacy Policy · Terms of Service
                </p>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-gradient-to-r from-[#00d4ff] to-[#00ff9d] text-[#0a0a0a] font-semibold text-sm hover:opacity-90 transition-opacity"
                >
                  <Send className="w-4 h-4" />
                  Send Message
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Bottom bar */}
        <div className="section-divider mb-8" />
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-600">
          <p>&copy; {new Date().getFullYear()} Veriaegis. All rights reserved.</p>
          <p className="text-center">
            SARO provides audit evidence only. Human review required before any regulatory
            submission.
          </p>
        </div>
      </div>
    </footer>
  )
}
