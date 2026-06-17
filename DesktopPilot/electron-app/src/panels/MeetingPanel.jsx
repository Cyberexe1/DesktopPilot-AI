import React, { useState, useEffect, useRef } from 'react'
import { Mic, MicOff, FileText, CheckSquare, Users, Clock, Send, Loader, Radio } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './MeetingPanel.css'

const API = 'http://localhost:8888'

const S = { IDLE: 'idle', RECORDING: 'recording', PROCESSING: 'processing', DONE: 'done', ERROR: 'error' }

export default function MeetingPanel() {
  const { addLog } = useAgent()
  const [step,       setStep]       = useState(S.IDLE)
  const [title,      setTitle]      = useState('')
  const [elapsed,    setElapsed]    = useState(0)
  const [result,     setResult]     = useState(null)
  const [error,      setError]      = useState('')
  const [emailTo,    setEmailTo]    = useState('')
  const timerRef = useRef(null)

  // Elapsed timer while recording
  useEffect(() => {
    if (step === S.RECORDING) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      clearInterval(timerRef.current)
      if (step !== S.RECORDING) setElapsed(0)
    }
    return () => clearInterval(timerRef.current)
  }, [step])

  const startMeeting = async () => {
    const t = title.trim() || `Meeting_${new Date().toLocaleTimeString()}`
    try {
      const res  = await fetch(`${API}/meeting/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: t }),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setStep(S.RECORDING)
      setError('')
      addLog(`Meeting recording started: ${t}`, 'info')
    } catch (e) {
      setError(e.message)
      setStep(S.ERROR)
    }
  }

  const stopAndProcess = async () => {
    setStep(S.PROCESSING)
    try {
      // Stop recording
      const stopRes  = await fetch(`${API}/meeting/stop`, { method: 'POST' })
      const stopData = await stopRes.json()
      if (stopData.error) throw new Error(stopData.error)

      const { wav_path, title: meetingTitle } = stopData.data
      addLog('Transcribing meeting audio...', 'info')

      // Process: transcribe + AI analysis + docx
      const procRes  = await fetch(`${API}/meeting/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wav_path, title: meetingTitle, send_email_to: emailTo }),
      })
      const procData = await procRes.json()
      if (procData.error) throw new Error(procData.error)

      setResult(procData.data)
      setStep(S.DONE)
      addLog(`Meeting notes created — ${procData.data.action_items?.length ?? 0} action items`, 'success')
    } catch (e) {
      setError(e.message)
      setStep(S.ERROR)
    }
  }

  const reset = () => {
    setStep(S.IDLE)
    setResult(null)
    setError('')
    setElapsed(0)
    setTitle('')
  }

  const fmt = (s) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`

  return (
    <div className="panel meeting-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Radio size={15} className="panel-title-icon" /> AI Meeting Assistant
        </span>
        {(step === S.DONE || step === S.ERROR) && (
          <button className="btn btn-ghost text-sm" onClick={reset}>↺ New meeting</button>
        )}
      </div>

      <div className="panel-body meeting-body">

        {/* ── IDLE — setup ── */}
        {step === S.IDLE && (
          <div className="meeting-setup card">
            <p className="section-label">Meeting Title</p>
            <input
              className="input"
              placeholder="e.g. Product Planning Q2"
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
            <p className="section-label" style={{ marginTop: '0.75rem' }}>
              Email Summary To (optional)
            </p>
            <input
              className="input"
              placeholder="team@company.com"
              value={emailTo}
              onChange={e => setEmailTo(e.target.value)}
            />
            <button className="btn btn-primary meeting-start-btn" onClick={startMeeting}>
              <Mic size={14} /> Start Recording
            </button>
            <p className="meeting-hint text-xs text-muted">
              DesktopPilot will record your microphone, transcribe via AWS Transcribe,
              extract action items with Bedrock, and generate a .docx file.
            </p>
          </div>
        )}

        {/* ── RECORDING ── */}
        {step === S.RECORDING && (
          <div className="meeting-recording">
            <div className="rec-orb-wrap">
              <div className="rec-orb">
                <Mic size={36} />
                <span className="rec-ring" />
                <span className="rec-ring rec-ring-2" />
                <span className="rec-ring rec-ring-3" />
              </div>
            </div>
            <p className="rec-timer font-mono">{fmt(elapsed)}</p>
            <p className="text-sm text-2">Recording in progress…</p>
            <p className="text-xs text-muted" style={{ marginTop: '0.25rem' }}>
              {title.trim() || 'Untitled Meeting'}
            </p>
            <button className="btn btn-danger meeting-stop-btn" onClick={stopAndProcess}>
              <MicOff size={14} /> End Meeting &amp; Process
            </button>
          </div>
        )}

        {/* ── PROCESSING ── */}
        {step === S.PROCESSING && (
          <div className="meeting-processing">
            <Loader size={40} className="spin text-accent" />
            <p className="text-sm" style={{ marginTop: '1rem' }}>Processing meeting…</p>
            <div className="proc-steps">
              {['Uploading audio to S3', 'Transcribing via AWS Transcribe', 'Analyzing with Bedrock Nova Pro', 'Generating .docx notes'].map((s, i) => (
                <div key={i} className="proc-step">
                  <Loader size={11} className="spin text-accent" />
                  <span className="text-xs text-2">{s}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── ERROR ── */}
        {step === S.ERROR && (
          <div className="card error-card">
            <span className="text-danger text-sm">{error}</span>
          </div>
        )}

        {/* ── DONE — results ── */}
        {step === S.DONE && result && (
          <div className="meeting-results">

            <div className="card card--glow-success result-summary">
              <p className="section-label">Summary</p>
              <p className="text-sm selectable" style={{ lineHeight: 1.7 }}>{result.summary}</p>
            </div>

            {result.action_items?.length > 0 && (
              <div className="card result-section" style={{ marginTop: '0.75rem' }}>
                <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <CheckSquare size={11} /> Action Items ({result.action_items.length})
                </p>
                <ul className="result-list">
                  {result.action_items.map((item, i) => (
                    <li key={i} className="result-item selectable">
                      <span className="result-checkbox">☐</span>
                      <span className="text-sm">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.decisions?.length > 0 && (
              <div className="card result-section" style={{ marginTop: '0.75rem' }}>
                <p className="section-label">Key Decisions</p>
                <ul className="result-list">
                  {result.decisions.map((d, i) => (
                    <li key={i} className="result-item selectable">
                      <span className="result-check text-accent">✓</span>
                      <span className="text-sm">{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.attendees?.length > 0 && (
              <div className="card result-section" style={{ marginTop: '0.75rem' }}>
                <p className="section-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Users size={11} /> Attendees
                </p>
                <div className="attendees-row">
                  {result.attendees.map((a, i) => (
                    <span key={i} className="badge badge-blue">{a}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="result-footer">
              <FileText size={12} className="text-muted" />
              <span className="text-xs text-muted">
                Notes saved to Desktop — {result.doc_path?.split('\\').pop()}
              </span>
            </div>
            {result.email && (
              <p className="text-xs text-muted" style={{ marginTop: '0.25rem' }}>
                📧 {result.email}
              </p>
            )}

          </div>
        )}

      </div>
    </div>
  )
}
