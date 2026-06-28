import React, { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Zap, CreditCard, Clock, Download, CheckCircle, Star, Wifi, WifiOff, RefreshCw,
         LayoutDashboard, History as HistoryIcon, Home, FileText, LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { API_URL, WS_URL } from '../lib/config'
import './Dashboard.css'

const API = API_URL

const PLANS = [
  {
    name: 'Starter', price: '$4.99', credits: 500,
    features: ['500 AI credits', 'Amazon Transcribe', 'Bedrock Claude Sonnet', 'Email support'],
    badge: null,
  },
  {
    name: 'Pro', price: '$14.99', credits: 2000,
    features: ['2,000 AI credits', 'Priority Bedrock access', 'DynamoDB memory sync', 'Priority support'],
    badge: 'Most Popular',
  },
  {
    name: 'Team', price: '$39.99', credits: 10000,
    features: ['10,000 AI credits', 'Multi-device sync', 'Team command history', 'Dedicated support'],
    badge: null,
  },
]

const MOCK_HISTORY = [
  { command: 'Prepare my EduPulse development environment', time: '10:32 AM', credits: 3 },
  { command: 'Open my latest resume',                       time: '10:18 AM', credits: 1 },
  { command: 'Open Gmail and draft a project update',       time: '09:55 AM', credits: 2 },
  { command: 'Open Bluetooth settings',                     time: '09:40 AM', credits: 1 },
  { command: 'Search AWS Bedrock documentation',            time: 'Yesterday', credits: 1 },
]

export default function Dashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [credits,    setCredits]    = useState(100)
  const [history,    setHistory]    = useState(MOCK_HISTORY)
  const [agentOnline,setAgentOnline]= useState(false)
  const [liveSteps,  setLiveSteps]  = useState([])
  const [activeTab,  setActiveTab]  = useState('overview')
  const [loading,    setLoading]    = useState(false)
  const [buyMsg,     setBuyMsg]     = useState('')
  const wsRef = useRef(null)

  // ── Poll agent health ──────────────────────────────────────────────────
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2000) })
        setAgentOnline(r.ok)
        if (r.ok) {
          // Fetch real credits
          const cr = await fetch(`${API}/credits`)
          const cd = await cr.json()
          if (cd.data?.credits_remaining != null) setCredits(cd.data.credits_remaining)
          // Fetch real history
          const hr = await fetch(`${API}/memory/commands`)
          const hd = await hr.json()
          if (hd.data?.commands) setHistory(hd.data.commands)
        }
      } catch { setAgentOnline(false) }
    }
    check()
    const id = setInterval(check, 10000)
    return () => clearInterval(id)
  }, [])

  // ── WebSocket for live execution steps ────────────────────────────────
  useEffect(() => {
    if (!agentOnline) return
    let ws
    const connect = () => {
      try {
        ws = new WebSocket(WS_URL)
        wsRef.current = ws
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data)
            if (msg.type === 'execution_start') {
              setLiveSteps(Array(msg.total).fill({ status: 'pending', message: '' }))
            } else if (msg.type === 'step_update') {
              setLiveSteps(prev => prev.map((s, i) =>
                i === msg.index ? { status: msg.success ? 'done' : 'failed', message: msg.message } : s
              ))
            } else if (msg.type === 'execution_done') {
              setTimeout(() => setLiveSteps([]), 5000)
            } else if (msg.type === 'plan_ready' && msg.credits_remaining != null) {
              setCredits(msg.credits_remaining)
            }
          } catch {}
        }
        ws.onclose = () => setTimeout(connect, 4000)
      } catch {}
    }
    connect()
    return () => ws?.close()
  }, [agentOnline])

  const refreshHistory = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/memory/commands`)
      const d = await r.json()
      if (d.data?.commands?.length) setHistory(d.data.commands)
    } catch {}
    setLoading(false)
  }

  const handleBuyPlan = async (planName) => {
    const userId = user?.user_id || 'default'
    setBuyMsg('')
    try {
      const res = await fetch(`${API}/credits/buy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, plan: planName }),
      })
      const data = await res.json()
      if (res.ok && data.data) {
        setCredits(data.data.credits_remaining)
        setBuyMsg(`✓ ${data.data.credits_added} credits added! Balance: ${data.data.credits_remaining}`)
        setTimeout(() => setBuyMsg(''), 5000)
      } else {
        setBuyMsg('Failed to purchase credits')
      }
    } catch (e) {
      setBuyMsg('Error: cannot connect to server')
    }
  }

  const commandsToday = history.filter(h => {
    const t = h.timestamp || h.time || ''
    return !t.includes('Yesterday') && !t.includes('2024') && !t.includes('2025')
  }).length

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const NAV_ITEMS = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={18} /> },
    { id: 'credits',  label: 'Credits',  icon: <CreditCard size={18} /> },
    { id: 'history',  label: 'History',  icon: <HistoryIcon size={18} /> },
  ]

  const TAB_TITLES = {
    overview: 'Overview',
    credits:  'Credits & Billing',
    history:  'Command History',
  }

  return (
    <div className="dash-layout">

      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="dash-sidebar">
        <Link to="/" className="dash-brand">
          <span className="dash-brand-mark" />
          <span className="dash-brand-text">ASTRA</span>
        </Link>

        <nav className="dash-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`dash-nav-item ${activeTab === item.id ? 'dash-nav-item--active' : ''}`}
              onClick={() => setActiveTab(item.id)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="dash-nav-divider" />

        <nav className="dash-nav">
          <Link to="/" className="dash-nav-item">
            <Home size={18} /><span>Home</span>
          </Link>
          <Link to="/docs" className="dash-nav-item">
            <FileText size={18} /><span>Docs</span>
          </Link>
        </nav>

        {/* Bottom: agent status + credits + user */}
        <div className="dash-sidebar-footer">
          <div className={`agent-pill ${agentOnline ? 'agent-online' : 'agent-offline'}`}>
            {agentOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
            <span>{agentOnline ? 'Agent Online' : 'Agent Offline'}</span>
          </div>

          <div className="dash-credits-box">
            <Zap size={15} className="text-accent" />
            <span className="credits-count">{credits}</span>
            <span className="text-muted text-xs">credits</span>
          </div>

          <div className="dash-user">
            <div className="dash-user-avatar">
              {(user?.name?.[0] || 'U').toUpperCase()}
            </div>
            <span className="dash-user-name">{user?.name?.split(' ')[0] || 'User'}</span>
            <button className="dash-logout" onClick={handleLogout} title="Sign out">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────────────── */}
      <main className="dash-main">
        <div className="dash-main-head">
          <h1 className="dash-title">{TAB_TITLES[activeTab]}</h1>
        </div>

        {/* Live execution feed — shown when agent is running a command */}
        {liveSteps.length > 0 && (
          <div className="card live-feed">
            <p className="section-label" style={{ marginBottom: '0.5rem' }}>
              ⚡ Live Execution
            </p>
            <ul className="live-steps">
              {liveSteps.map((s, i) => (
                <li key={i} className={`live-step live-step--${s.status}`}>
                  <span className="live-dot" />
                  <span className="text-sm">{s.message || `Step ${i + 1}`}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

      {/* Overview */}
      {activeTab === 'overview' && (
        <div className="dash-section">
          <div className="overview-grid">
            <StatCard icon={<Zap size={18} />}   label="Credits Left"   value={credits}        color="accent"  />
            <StatCard icon={<Clock size={18} />}  label="Commands Today" value={commandsToday}  color="success" />
            <StatCard icon={<Star size={18} />}   label="Plan"           value="Free"           color="warning" />
          </div>

          <div className="card dash-card">
            <h3 className="dash-card-title">Recent Commands</h3>
            <ul className="history-list">
              {history.slice(0, 3).map((h, i) => <HistoryItem key={i} item={h} />)}
            </ul>
          </div>

          <div className="card dash-card download-card">
            <div className="download-info">
              <Download size={20} className="text-accent" />
              <div>
                <h3 className="dash-card-title">Desktop Agent</h3>
                <p className="text-sm text-muted">
                  Download and install the Windows agent to start using voice commands.
                </p>
              </div>
            </div>
            <a href={import.meta.env.VITE_DOWNLOAD_URL || '#'} className="btn-primary" download>
              <Download size={15} /> Download for Windows
            </a>
          </div>
        </div>
      )}

      {/* Credits */}
      {activeTab === 'credits' && (
        <div className="dash-section">
          <div className="credits-bar-row">
            <span className="text-sm text-muted">Credits used this month</span>
            <span className="text-sm">{Math.max(0, 100 - credits)} / 100</span>
          </div>
          <div className="credits-bar">
            <div className="credits-bar-fill"
              style={{ width: `${Math.min(100, Math.max(0, ((100 - credits) / 100) * 100))}%` }} />
          </div>

          <h2 className="plans-title">Buy More Credits</h2>
          {buyMsg && (
            <div className="buy-success-msg">{buyMsg}</div>
          )}
          <div className="plans-grid">
            {PLANS.map((plan, i) => (
              <div key={i} className={`card plan-card ${plan.badge ? 'plan-card--featured' : ''}`}>
                {plan.badge && <span className="plan-badge">{plan.badge}</span>}
                <h3 className="plan-name">{plan.name}</h3>
                <div className="plan-price">
                  <span className="price-amount">{plan.price}</span>
                  <span className="text-muted text-sm">/month</span>
                </div>
                <div className="plan-credits">
                  <Zap size={13} className="text-accent" />
                  <span className="text-sm">{plan.credits.toLocaleString()} credits</span>
                </div>
                <ul className="plan-features">
                  {plan.features.map((f, j) => (
                    <li key={j}>
                      <CheckCircle size={12} className="text-success" />
                      <span className="text-sm">{f}</span>
                    </li>
                  ))}
                </ul>
                <button
                  className={`btn-plan ${plan.badge ? 'btn-plan--featured' : ''}`}
                  onClick={() => handleBuyPlan(plan.name.toLowerCase())}
                >
                  <CreditCard size={14} /> Get {plan.name}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      {activeTab === 'history' && (
        <div className="dash-section">
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3 className="dash-card-title">Command History</h3>
              <button className="btn-refresh" onClick={refreshHistory} disabled={loading}>
                <RefreshCw size={13} className={loading ? 'spin' : ''} />
                Refresh
              </button>
            </div>
            {agentOnline
              ? <p className="text-xs text-muted" style={{ marginBottom: '0.75rem' }}>
                  Live data from local agent. Phase 3: syncs to DynamoDB.
                </p>
              : <p className="text-xs text-muted" style={{ marginBottom: '0.75rem' }}>
                  Agent offline — showing cached data.
                </p>
            }
            <ul className="history-list">
              {history.map((h, i) => <HistoryItem key={i} item={h} />)}
            </ul>
          </div>
        </div>
      )}
      </main>
    </div>
  )
}

function StatCard({ icon, label, value, color }) {
  return (
    <div className="card stat-card">
      <div className={`stat-icon stat-icon--${color}`}>{icon}</div>
      <div>
        <p className="stat-value">{value}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    </div>
  )
}

function HistoryItem({ item }) {
  const time    = item.timestamp || item.time || ''
  const credits = item.credits_used ?? item.credits ?? 1
  return (
    <li className="history-item">
      <div className="history-dot" />
      <div className="history-content">
        <p className="text-sm">{item.command}</p>
        <div className="history-meta">
          <span className="text-xs text-muted">{time}</span>
          <span className="history-credits">
            <Zap size={10} /> {credits} credit{credits !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </li>
  )
}
