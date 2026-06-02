'use client'

import { useEffect, useRef } from 'react'
import { Shield, Play, ArrowRight } from 'lucide-react'

const SARO_URL = 'https://saro-production-2993.up.railway.app/'

export default function Hero() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  /* Animated neural-shield particle canvas */
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    interface Particle { x: number; y: number; vx: number; vy: number; r: number; a: number }
    const particles: Particle[] = Array.from({ length: 80 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 2 + 0.5,
      a: Math.random(),
    }))

    let raf: number
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach((p) => {
        p.x += p.vx; p.y += p.vy
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(0,212,255,${p.a * 0.6})`
        ctx.fill()
      })
      /* Draw connecting lines */
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x
          const dy = particles[i].y - particles[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 120) {
            ctx.beginPath()
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.strokeStyle = `rgba(0,212,255,${(1 - dist / 120) * 0.12})`
            ctx.lineWidth = 0.5
            ctx.stroke()
          }
        }
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [])

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden neural-grid">
      {/* Particle canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />

      {/* Radial glow blobs */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#00d4ff08] rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-[#00ff9d06] rounded-full blur-[100px] pointer-events-none" />

      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 text-center pt-24 pb-16">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00d4ff30] bg-[#00d4ff0a] text-[#00d4ff] text-sm font-medium mb-8">
          <Shield className="w-3.5 h-3.5" />
          Enterprise AI Governance Platform
        </div>

        {/* Headline */}
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-tight mb-6 tracking-tight">
          <span className="text-white">Orchestrate. Govern.</span>
          <br />
          <span className="gradient-text text-glow">Protect.</span>
          <br />
          <span className="text-white text-4xl sm:text-5xl lg:text-6xl font-bold">AI at Enterprise Scale.</span>
        </h1>

        {/* Sub-headline */}
        <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          SARO is the world&apos;s most advanced AI risk orchestrator — providing real-time threat
          detection, automated governance, and compliance automation for every AI system in your
          enterprise.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <a
            href={SARO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-[#00d4ff] to-[#00ff9d] text-[#0a0a0a] font-bold text-base hover:opacity-90 transition-all shadow-xl hover:shadow-[0_0_40px_rgba(0,212,255,0.4)] hover:scale-105"
          >
            Sign In to SARO
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </a>
          <button
            onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
            className="flex items-center gap-2 px-8 py-3.5 rounded-xl border border-[#00d4ff30] text-[#00d4ff] font-semibold text-base hover:bg-[#00d4ff0f] transition-colors"
          >
            <Play className="w-4 h-4 fill-current" />
            Watch 90-second Demo
          </button>
        </div>

        {/* Trust metrics */}
        <div className="flex flex-wrap justify-center gap-8 text-center">
          {[
            { val: '99.9%', label: 'Risk Detection Rate' },
            { val: '< 50ms', label: 'Real-time Scan Latency' },
            { val: '80%', label: 'Faster Compliance' },
            { val: 'Zero-trust', label: 'AI Governance Model' },
          ].map((m) => (
            <div key={m.label} className="flex flex-col items-center">
              <span className="text-2xl font-extrabold text-[#00d4ff]">{m.val}</span>
              <span className="text-xs text-slate-500 mt-1">{m.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scroll chevron */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <div className="w-6 h-10 rounded-full border-2 border-[#00d4ff30] flex items-start justify-center pt-2">
          <div className="w-1 h-2 bg-[#00d4ff] rounded-full" />
        </div>
      </div>
    </section>
  )
}
