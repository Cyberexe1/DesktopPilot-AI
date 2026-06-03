import React from 'react'
import { Link } from 'react-router-dom'
import { Download, LayoutDashboard, Mic, Brain, GitBranch, FolderSearch, Globe, ShieldCheck, ArrowDown, Zap, CheckCircle2, Circle } from 'lucide-react'
import './LandingPage.css'

const DOWNLOAD_URL = import.meta.env.VITE_DOWNLOAD_URL || '#'

const features = [
  { icon: <Mic size={28} />,          title: 'Voice Controlled',      desc: 'Zero-latency voice interpretation powered by Whisper local processing.' },
  { icon: <Brain size={28} />,         title: 'AI Planning',           desc: 'Automatically breaks down complex vocal requests into executable technical steps.' },
  { icon: <GitBranch size={28} />,     title: 'Multi-Step Execution',  desc: 'Handles sequential tasks across multiple applications without intervention.' },
  { icon: <FolderSearch size={28} />,  title: 'File Intelligence',     desc: 'Index and query your local file system using natural language queries.' },
  { icon: <Globe size={28} />,         title: 'Browser Automation',    desc: 'Control Chrome to extract data, compose emails, or perform web actions.' },
  { icon: <ShieldCheck size={28} />,   title: 'Safe by Design',        desc: 'All computations run locally. Sensitive actions require your approval.' },
]

const steps = [
  { icon: <Download size={22} />,      title: 'Download & Install',  desc: 'Lightweight client for Windows.' },
  { icon: <Mic size={22} />,           title: 'Speak a Command',     desc: 'Just say what you need in plain English.' },
  { icon: <CheckCircle2 size={22} />,  title: 'Review the Plan',     desc: 'AI verifies steps before touching your files.' },
  { icon: <Zap size={22} />,           title: 'Watch it Execute',    desc: 'Sit back as Cipher executes the flow.', active: true },
]

export default function LandingPage() {
  return (
    <main className="landing">

      {/* Hero */}
      <section className="hero">
        <div className="hero-badge">
          <span className="badge-label">NEW v2.4 RELEASE</span>
          <span className="badge-sep">|</span>
          <span className="badge-sub">Advanced Multi-Step Reasoning Enabled</span>
        </div>

        <h1 className="hero-title">
          Your Desktop, Controlled by <span className="gradient-text">Voice</span>
        </h1>

        <p className="hero-sub">
          The first neural interface for your local environment. Automate complex workflows,
          manage files, and navigate applications with low-latency voice execution.
        </p>

        <div className="hero-actions">
          <a href={DOWNLOAD_URL} className="btn-primary-hero" download>
            <Download size={18} /> Download for Windows
          </a>
          <Link to="/dashboard" className="btn-ghost-hero">
            <LayoutDashboard size={18} /> Open Dashboard
          </Link>
        </div>

        {/* Terminal */}
        <div className="terminal">
          <div className="terminal-header">
            <div className="terminal-dots">
              <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
            </div>
            <span className="terminal-label">CIPHER-CLI / EXECUTION-LOG</span>
            <div />
          </div>
          <div className="terminal-body">
            <div className="term-line">
              <span className="term-prompt">&gt;</span>
              <span className="term-cmd">cipher listen --active</span>
            </div>
            <div className="term-user">
              User: "Hey Cipher, open the react project, start the dev server and show me the preview."
            </div>
            <div className="term-steps">
              <div className="term-step done">
                <CheckCircle2 size={16} />
                <span>Initializing directory: /Users/admin/projects/next-app</span>
              </div>
              <div className="term-step done">
                <CheckCircle2 size={16} />
                <span>Running: `npm run dev` (Port 3000 detected)</span>
              </div>
              <div className="term-step active">
                <Circle size={16} />
                <span>Launching browser: http://localhost:3000</span>
                <span className="cursor-blink" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features-section">
        <h2 className="section-heading">Powerful by Command</h2>
        <div className="features-grid">
          {features.map((f, i) => (
            <div key={i} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3 className="feature-title">{f.title}</h3>
              <p className="feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="steps-section">
        <h2 className="section-heading">Engineered for Speed</h2>
        <div className="steps-row">
          {steps.map((s, i) => (
            <div key={i} className="step-item">
              <div className={`step-circle ${s.active ? 'step-circle-active' : ''}`}>
                {s.icon}
              </div>
              <h4 className="step-title">{s.title}</h4>
              <p className="step-desc">{s.desc}</p>
              {i < steps.length - 1 && <div className="step-connector" />}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div className="cta-card">
          <h2 className="cta-title">Ready to speak your workflow?</h2>
          <p className="cta-sub">
            Join developers automating their daily grind with the power of voice. Free to start, forever local.
          </p>
          <div className="cta-actions">
            <a href={DOWNLOAD_URL} className="btn-primary-hero" download>Start Free Trial</a>
            <Link to="/dashboard" className="btn-ghost-hero">View Pricing</Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <span className="footer-name">DesktopPilot AI</span>
            <p className="footer-copy">© 2025 DesktopPilot AI. Engineered for performance.</p>
          </div>
          <div className="footer-links">
            <a href="#">Terms</a>
            <a href="#">Privacy</a>
            <a href="#">Status</a>
            <a href="#">API</a>
          </div>
        </div>
      </footer>
    </main>
  )
}
