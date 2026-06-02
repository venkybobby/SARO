'use client'

import { useState, useEffect } from 'react'
import { Menu, X, Shield } from 'lucide-react'

const SARO_URL = 'https://saro-production-2993.up.railway.app/'

const navLinks = [
  { label: 'Product', href: '#features' },
  { label: 'Features', href: '#capabilities' },
  { label: 'Solutions', href: '#how-it-works' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Resources', href: '#faq' },
]

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[#0a0a0a]/95 backdrop-blur-md border-b border-[#00d4ff15] shadow-lg'
          : 'bg-transparent'
      }`}
    >
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
        {/* Logo */}
        <a href="#" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00d4ff] to-[#00ff9d] flex items-center justify-center shadow-lg group-hover:shadow-[0_0_20px_rgba(0,212,255,0.5)] transition-shadow">
            <Shield className="w-4 h-4 text-[#0a0a0a]" strokeWidth={2.5} />
          </div>
          <span className="font-bold text-white text-lg tracking-tight">
            SARO <span className="text-[#00d4ff]">by Veriaegis</span>
          </span>
        </a>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((l) => (
            <a
              key={l.label}
              href={l.href}
              className="text-sm text-slate-400 hover:text-[#00d4ff] transition-colors font-medium"
            >
              {l.label}
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          <a
            href={SARO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="px-5 py-2 rounded-lg bg-gradient-to-r from-[#00d4ff] to-[#00ff9d] text-[#0a0a0a] font-semibold text-sm hover:opacity-90 transition-opacity shadow-lg hover:shadow-[0_0_20px_rgba(0,212,255,0.4)]"
          >
            Sign In to SARO →
          </a>
        </div>

        {/* Mobile toggle */}
        <button
          className="md:hidden text-slate-400 hover:text-white p-2"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-[#0f0f0f] border-t border-[#1a1a2e] px-4 py-4 space-y-3">
          {navLinks.map((l) => (
            <a
              key={l.label}
              href={l.href}
              onClick={() => setOpen(false)}
              className="block text-sm text-slate-400 hover:text-[#00d4ff] py-2 font-medium"
            >
              {l.label}
            </a>
          ))}
          <a
            href={SARO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="block text-center mt-3 px-5 py-2.5 rounded-lg bg-gradient-to-r from-[#00d4ff] to-[#00ff9d] text-[#0a0a0a] font-semibold text-sm"
          >
            Sign In to SARO →
          </a>
        </div>
      )}
    </header>
  )
}
