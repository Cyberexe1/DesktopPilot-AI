import React, { useState, useEffect, useCallback } from 'react'
import { Target, Play, Square, Clock, BarChart2, Zap, RefreshCw } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './FocusPanel.css'

const API = 'http://localhost:8888'

export default function FocusPanel() {
  const { addLog } = useAgent()
  const [status,    setStatus]    = useState({ active: false })
  const [sessions,  setSessions]  = useState([])
  const [loading,   setLoading]   = useState(false)
  const [starting,  setStarting]  = useState(false)
  const [stopping,  setStopping]  = useState(false)

  // Config
  const [goal,      setGoal]      = useState('')
  const [hours,     setHours]     = useState(2)
  const [focusMin,  setFocusMin]  = useState(25)
  const [breakMin,  setBreakMin]  = useState(5)

  const loadStatus = useCallback(async () => {
    try {
      const [sRes, sessRes] = await Promise.all([
        fetch(`${API}/focus/status`),
        fetch(`${API}/focus/sessions`),
      ])
      const sData    = await sRes.json()
      const sessData = await sessRes.json()
      setStatus(sData.data ?? { active: false })
      setSessions(sessData.data?.sessions ?? [])
    } catch {}
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  // Poll status while active
  useEffect(() => {
    if (!status.active) return
    const id = setInterval(loadStatus, 2000)
    return () => clearInterval(id)
  }, [status.active, loadStatus])

  const handleStart = async () => {
    setStarting(true)
    try {
      const res  = await fetch(`${API}/focus/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_hours: hours, goal, focus_min: focusMin, break_min: breakMin }),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      addLog(`Focus mode started — ${hours}h`, 'success')
      await loadStatus()
    } catch (e) {
      addLog('Focus start failed: ' + e.message, 'error')
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async () => {
    setStopping(true)
    try {
      const res  = await fetch(`${API}/focus/stop`, { method: 'POST' })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      addLog('Focus session ended', 'info')
      await loadStatus()
    } catch (e) {
      addLog('Focus stop failed: ' + e.message, 'error')
    } finally {
      setStopping(false)
    }
  }

  const fmtRemaining = (sec) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const cycleProgress = status.active
    ? Math.max(0, Math.min(100,
        ((((status.mode === 'focus' ? focusMin : breakMin) * 60) - status.remaining_sec)
        / ((status.mode === 'focus' ? focusMin : breakMin) * 60)) * 100
      ))
    : 0

  return (
    <div className="panel focus-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Target size={15} className="panel-title-icon" /> Focus Mode
        </span>
        <button className="btn-icon" onClick={loadStatus} title="Refresh">
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="panel-body focus-body">

        {/* ── ACTIVE — live timer ── */}
        {status.active && (
          <div className="focus-active">
            <div className={`focus-mode-badge ${status.mode === 'focus' ? 'badge-focus' : 'badge-break'}`}>
              {status.mode === 'focus' ? '🎯 Focus Time' : '☕ Break Time'}
            </div>

            {/* Radial timer ring */}
            <div className="focus-ring-wrap">
              <svg className="focus-ring-svg" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="54" className="focus-ring-track" />
                <circle
                  cx="60" cy="60" r="54"
                  className={`focus-ring-fill ${status.mode === 'focus' ? 'ring-focus' : 'ring-break'}`}
                  strokeDasharray={`${2 * Math.PI * 54}`}
                  strokeDashoffset={`${2 * Math.PI * 54 * (1 - cycleProgress / 100)}`}
                />
              </svg>
              <div className="focus-ring-content">
                <span className="focus-time">{fmtRemaining(status.remaining_sec)}</span>
                <span className="focus-label text-xs text-muted">
                  Cycle {status.cycle}/{status.total_cycles}
                </span>
              </div>
            </div>

            {status.goal && (
              <p className="focus-goal text-sm text-2">🎯 {status.goal}</p>
            )}

            <button
              className="btn btn-danger focus-stop-btn"
              onClick={handleStop}
              disabled={stopping}
            >
              {stopping ? <RefreshCw size={13} className="spin" /> : <Square size={13} />}
              End Session
            </button>
          </div>
        )}

        {/* ── IDLE — setup ── */}
        {!status.active && (
          <div className="focus-setup">
            <div className="card focus-config">
              <p className="section-label">Session Goal (optional)</p>
              <input
                className="input"
                placeholder="e.g. Finish the landing page"
                value={goal}
                onChange={e => setGoal(e.target.value)}
              />

              <div className="focus-config-row">
                <div className="focus-config-field">
                  <p className="section-label">Duration (hours)</p>
                  <div className="focus-stepper">
                    <button className="stepper-btn" onClick={() => setHours(h => Math.max(0.5, h - 0.5))}>−</button>
                    <span className="stepper-val">{hours}h</span>
                    <button className="stepper-btn" onClick={() => setHours(h => Math.min(8, h + 0.5))}>+</button>
                  </div>
                </div>
                <div className="focus-config-field">
                  <p className="section-label">Focus (min)</p>
                  <div className="focus-stepper">
                    <button className="stepper-btn" onClick={() => setFocusMin(m => Math.max(10, m - 5))}>−</button>
                    <span className="stepper-val">{focusMin}m</span>
                    <button className="stepper-btn" onClick={() => setFocusMin(m => Math.min(60, m + 5))}>+</button>
                  </div>
                </div>
                <div className="focus-config-field">
                  <p className="section-label">Break (min)</p>
                  <div className="focus-stepper">
                    <button className="stepper-btn" onClick={() => setBreakMin(m => Math.max(3, m - 2))}>−</button>
                    <span className="stepper-val">{breakMin}m</span>
                    <button className="stepper-btn" onClick={() => setBreakMin(m => Math.min(30, m + 2))}>+</button>
                  </div>
                </div>
              </div>

              <div className="focus-calc">
                <Zap size={11} className="text-accent" />
                <span className="text-xs text-2">
                  {Math.round((hours * 60) / (focusMin + breakMin))} cycles ·{' '}
                  {Math.round((hours * 60 * focusMin) / (focusMin + breakMin))}m focused
                </span>
              </div>

              <div className="focus-blocked-info">
                <p className="text-xs text-muted">
                  Will close: Discord, Spotify, WhatsApp, Slack · Sets Windows DND on
                </p>
              </div>

              <button
                className="btn btn-primary focus-start-btn"
                onClick={handleStart}
                disabled={starting}
              >
                {starting
                  ? <RefreshCw size={13} className="spin" />
                  : <Play size={13} />
                }
                Start Focus Mode
              </button>
            </div>

            {/* ── Past sessions ── */}
            {sessions.length > 0 && (
              <div className="focus-history">
                <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <BarChart2 size={11} /> Past Sessions
                </p>
                {sessions.map((s, i) => (
                  <div key={i} className="card session-card">
                    <div className="session-row">
                      <div>
                        <p className="text-sm" style={{ fontWeight: 600 }}>
                          {s.cycles_completed}/{s.total_cycles} cycles
                        </p>
                        {s.goal && <p className="text-xs text-muted">{s.goal}</p>}
                      </div>
                      <div className="session-stats">
                        <span className="badge badge-red">{s.total_focus_min}m focused</span>
                        <span className="badge badge-blue">{s.efficiency}</span>
                      </div>
                    </div>
                    {s.ai_insight && (
                      <p className="text-xs text-2" style={{ marginTop: '0.4rem', fontStyle: 'italic' }}>
                        "{s.ai_insight}"
                      </p>
                    )}
                    <p className="text-xs text-muted" style={{ marginTop: '0.2rem' }}>{s.date}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
