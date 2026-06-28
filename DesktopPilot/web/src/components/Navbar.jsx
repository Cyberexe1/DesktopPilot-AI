import React, { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Zap, LogOut, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { API_URL } from '../lib/config'
import './Navbar.css'

export default function Navbar() {
  const { pathname }                        = useLocation()
  const navigate                            = useNavigate()
  const { user, isAuthenticated, logout }   = useAuth()
  const [agentConnected, setAgentConnected] = useState(false)
  const [credits,        setCredits]        = useState(null)

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(2000) })
        const ok  = res.ok
        setAgentConnected(ok)
        if (ok) {
          const cr = await fetch(`${API_URL}/credits`)
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

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <header className="nav-header">
      <nav className="nav-inner">
        <div className="nav-left">
          <Link to="/" className="nav-brand">DesktopPilot AI</Link>
          <div className="nav-links">
            <Link to="/"          className={pathname === '/' ? 'nav-link nav-link-active' : 'nav-link'}>Home</Link>
            {isAuthenticated && (
              <Link to="/dashboard" className={pathname === '/dashboard' ? 'nav-link nav-link-active' : 'nav-link'}>Dashboard</Link>
            )}
            <Link to="/docs"      className={pathname === '/docs' ? 'nav-link nav-link-active' : 'nav-link'}>Docs</Link>
          </div>
        </div>

        <div className="nav-right">
          <div className={`agent-badge ${agentConnected ? 'agent-online' : 'agent-offline'}`}>
            <span className="agent-dot-nav" />
            <span className="agent-label">
              {agentConnected ? 'Agent Connected' : 'Agent Offline'}
            </span>
          </div>

          {agentConnected && credits !== null && (
            <div className="credits-badge-nav">
              <Zap size={12} />
              <span>{credits.toLocaleString()} CREDITS</span>
            </div>
          )}

          {isAuthenticated ? (
            <div className="user-section">
              <span className="user-name">{user?.name?.split(' ')[0]}</span>
              <button className="logout-btn" onClick={handleLogout} title="Sign out">
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <Link to="/login" className="signin-btn">Sign In</Link>
          )}
        </div>
      </nav>
    </header>
  )
}
