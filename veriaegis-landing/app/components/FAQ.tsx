'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

const faqs = [
  {
    q: 'What exactly does SARO scan?',
    a: 'SARO accepts the raw prompt and raw output from any AI model or agent interaction. It scores every pair (0–100 risk scale), generates a TRACE timeline, and returns remediation guidance. SARO never calls external AI models itself — it operates on the text you submit.',
  },
  {
    q: 'Does SARO write to or modify my systems?',
    a: 'No. SARO operates in a strictly read-only integration posture. It never writes to client systems, databases, or AI models. All governance actions are advisory — your team retains full control over enforcement.',
  },
  {
    q: 'How does SARO handle data privacy?',
    a: 'SARO processes prompt and output data exclusively for risk scoring. No data is used for model training. All data is encrypted in transit and at rest. Enterprise plans support on-premises deployment for maximum data sovereignty.',
  },
  {
    q: 'Does SARO certify compliance with EU AI Act or NIST?',
    a: 'No — and we are transparent about this. SARO provides audit evidence, risk scoring, and framework-mapped findings that support compliance workflows. Actual certification and regulatory determination requires qualified human reviewers. SARO never issues or implies regulatory certificates.',
  },
  {
    q: 'What AI models and agents does SARO support?',
    a: 'SARO is model-agnostic. It integrates via a simple REST API that accepts prompt + output pairs from any LLM, AI agent, or automated system — GPT-4, Claude, Gemini, Llama, custom models, or multi-agent pipelines.',
  },
  {
    q: 'How quickly is SARO\'s risk scoring?',
    a: 'Synchronous scan results are returned in under 50ms on average. SARO is designed for real-time integration into production AI pipelines without introducing meaningful latency.',
  },
  {
    q: 'What is a TRACE timeline?',
    a: 'The TRACE timeline is SARO\'s immutable, SHA-256 hash-chained audit record for every AI interaction. It captures the full decision chain — prompt, output, risk score, rule triggers, and remediation guidance — in a forensically verifiable format for human auditor review.',
  },
  {
    q: 'Can SARO integrate with our existing security and compliance tooling?',
    a: 'Yes. SARO exposes a full REST API and supports webhook-based alerting. Enterprise customers receive dedicated integration support for SIEM, GRC platforms, ticketing systems, and custom enterprise tooling.',
  },
]

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(null)

  return (
    <section id="faq" className="py-24 px-4 sm:px-6">
      <div className="section-divider mb-24" />

      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#00d4ff30] bg-[#00d4ff0a] text-[#00d4ff] text-sm font-medium mb-4">
            FAQ
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-4">
            Common questions
            <br />
            <span className="gradient-text">answered honestly</span>
          </h2>
        </div>

        <div className="space-y-3">
          {faqs.map((f, i) => (
            <div
              key={i}
              className="rounded-xl border border-[#1a1a2e] bg-[#0f0f0f] overflow-hidden"
            >
              <button
                className="w-full flex items-center justify-between px-6 py-4 text-left"
                onClick={() => setOpen(open === i ? null : i)}
              >
                <span className="text-sm font-semibold text-white pr-4">{f.q}</span>
                <ChevronDown
                  className={`w-4 h-4 text-[#00d4ff] flex-shrink-0 transition-transform ${
                    open === i ? 'rotate-180' : ''
                  }`}
                />
              </button>
              {open === i && (
                <div className="px-6 pb-5">
                  <p className="text-slate-400 text-sm leading-relaxed">{f.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
