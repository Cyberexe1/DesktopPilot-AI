import React from 'react'
import { Link } from 'react-router-dom'
import { Download, Mic, Zap, Brain, FolderOpen, Globe, Shield, CreditCard } from 'lucide-react'
import './LandingPage.css'

const DOWNLOAD_URL = import.meta.env.VITE_DOWNLOAD_URL || '#'

const features = [
  { icon: <Mic size={22} />, title: 'Voice Controlled', desc: 'Speak naturally. DesktopPilot understands intent, not just keywords.' },
  { icon: <Brain size={22} />, title: 'AI Planning', desc: 'Amazon Bedrock (Claude) converts your command into a multi-step execution plan.' },
  { icon: <Zap size={22} />, title: 'Multi-Step Execution', desc: 'One command can open VS Code, start a server, and launch your browser.' },
  { icon: <FolderOpen size={22} />, title: 'File Intelligence', desc: 'Instantly finds files across your entire machine using a smart local index.' },
  { icon: <Globe size={22} />, title: 'Browser Automation', desc: 'Opens websites, searches the web, and drafts emails on your behalf.' },
  { icon: <Shield size={22} />, title: 'Safe by Design', desc: 'Sensitive actions always require your approval before execution.' },
]

export default function LandingPage() {
  return (
    <main className="landing">
      {/* Hero */}
      <section className="hero container">
        <div className="hero-badge badge badge-info">
          <Zap size={12} /> Powered by AWS Bedrock + Transcribe
        </div>
        <h1 className="hero-title">
          Your Desktop,<br />
          <span className="gradient-text">Controlled by Voice</span>
        </h1>
        <p className="hero-sub">
          DesktopPilot AI is an autonomous agent that listens to your natural language commands
          and executes complex multi-step workflows across your Windows desktop.
        </p>
        <div className="hero-actions">
          <a href={DOWNLOAD_URL} className="btn-primary" download>
            <Download size={18} /> Download for Windows
          </a>
          <Link to="/dashboard" className="btn-secondary">
            Open Dashboard →
          </Link>
        </div>
        <p className="hero-note text-muted text-sm">
          Free during hackathon · Windows 10/11 · Requires local agent
        </p>
      </section>

      {/* Demo preview */}
      <section className="demo-section container">
        <div className="demo-terminal card">
          <div className="terminal-bar">
            <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
            <span className="terminal-title text-muted text-sm">DesktopPilot — Live Execution</span>
          </div>
          <div className="terminal-body">
            <p className="terminal-prompt">
              <span className="prompt-icon">🎤</span>
              <span className="prompt-text">"Prepare my EduPulse development environment."</span>
            </p>
            <div className="terminal-steps">
              {[
                { done: true,  label: 'Found project: EduPulse at D:/Projects/EduPulse' },
                { done: true,  label: 'Opened VS Code' },
                { done: true,  label: 'Running: python manage.py runserver' },
                { done: true,  label: 'Server ready at http://localhost:8000' },
                { done: true,  label: 'Opened Chrome → localhost:8000' },
              ].map((step, i) => (
                <div key={i} className="terminal-step">
                  <span className={step.done ? 'step-done' : 'step-pending'}>
                    {step.done ? '✓' : '○'}
                  </span>
                  <span>{step.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features-section container">
        <h2 className="section-title text-center">Everything you need to go hands-free</h2>
        <div className="features-grid">
          {features.map((f, i) => (
            <div key={i} className="feature-card card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p className="text-muted text-sm mt-1">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="how-section container">
        <h2 className="section-title text-center">How it works</h2>
        <div className="steps-row">
          {[
            { n: '01', title: 'Download & Install', desc: 'Install the Windows agent. It runs silently in the background.' },
            { n: '02', title: 'Speak a Command', desc: 'Click the mic button on the dashboard and say what you want.' },
            { n: '03', title: 'Review the Plan', desc: 'AI generates a step-by-step plan. Approve sensitive actions.' },
            { n: '04', title: 'Watch it Execute', desc: 'The agent carries out every step and reports back in real time.' },
          ].map((s, i) => (
            <div key={i} className="step-item">
              <div className="step-number">{s.n}</div>
              <h4>{s.title}</h4>
              <p className="text-muted text-sm mt-1">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section container text-center">
        <h2>Ready to automate your desktop?</h2>
        <p className="text-muted mt-1">Download the agent and open the dashboard to get started.</p>
        <div className="hero-actions mt-3">
          <a href={DOWNLOAD_URL} className="btn-primary" download>
            <Download size={18} /> Download for Windows
          </a>
          <Link to="/docs" className="btn-secondary">Read the Docs</Link>
        </div>
      </section>

      <footer className="landing-footer text-center text-muted text-sm">
        <p>Built with Amazon Bedrock · Transcribe · DynamoDB · Lambda · Step Functions</p>
        <p className="mt-1">© 2025 DesktopPilot AI</p>
      </footer>
    </main>
  )
}
