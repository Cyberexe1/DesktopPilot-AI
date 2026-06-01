import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Cpu, Zap } from 'lucide-react'
import './Navbar.css'

export default function Navbar() {
  const { pathname }                        = useLocation()
  const [agentConnected, setAgentConnected] = useState(false)
  const [credits,        setCredits]        = useState(null)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('http://localhost:8000/health', { signal: AbortSignal.timeout(2000) })
        const ok  = res.ok
        setAgentConnected(ok)
        if (ok) {
          const cr = await fetch('http://localhost:8000/credits')
          const cd = await cr.json()
          if (cd.data?.credits_remaining != null) setCredits(cd.data.credits_remaining)
        }
      } catch {
        setAgentConnected(false)
      }
    }
    check()
    const interval = setInterval(check, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <nav className="navbar">
      <div className="navbar-inner container">
        <Link to="/" className="navbar-brand">
          <Cpu size={20} className="brand-icon" />
          <span>DesktopPilot <span className="brand-ai">AI</span></span>
        </Link>

        <div className="navbar-links">
          <Link to="/"          className={pathname === '/'          ? 'nav-link active' : 'nav-link'}>Home</Link>
          <Link to="/dashboard" className={pathname === '/dashboard' ? 'nav-link active' : 'nav-link'}>Dashboard</Link>
          <Link to="/docs"      className={pathname === '/docs'      ? 'nav-link active' : 'nav-link'}>Docs</Link>
        </div>

        <div className="navbar-status">
          {agentConnected && credits !== null && (
            <div className="navbar-credits">
              <Zap size={12} />
              <span className="text-sm">{credits}</span>
            </div>
          )}
          <span className={`agent-dot ${agentConnected ? 'connected' : 'disconnected'}`} />
          <span className="text-sm text-muted">
            {agentConnected ? 'Agent Connected' : 'Agent Offline'}
          </span>
        </div>
      </div>
    </nav>
  )
}
