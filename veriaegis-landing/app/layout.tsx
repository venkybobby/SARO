import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SARO — Smart AI Risk Orchestrator | Veriaegis',
  description:
    'Enterprise AI Governance Platform. Real-time risk orchestration, threat protection, and compliance automation for secure AI deployment.',
  keywords: [
    'AI governance', 'AI risk management', 'enterprise AI security',
    'prompt injection protection', 'AI compliance', 'SARO', 'Veriaegis',
  ],
  authors: [{ name: 'Veriaegis' }],
  openGraph: {
    type: 'website',
    url: 'https://veriaegis.ai',
    title: 'SARO — Smart AI Risk Orchestrator | Veriaegis',
    description:
      'Enterprise AI Governance Platform. Real-time risk orchestration, threat protection, and compliance automation for secure AI deployment.',
    siteName: 'Veriaegis',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'SARO — Smart AI Risk Orchestrator | Veriaegis',
    description: 'Enterprise AI Governance Platform.',
  },
  robots: { index: true, follow: true },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="bg-[#0a0a0a] text-slate-200 antialiased">{children}</body>
    </html>
  )
}
