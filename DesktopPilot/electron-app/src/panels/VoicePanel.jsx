import React, { useState, useRef } from 'react'
import { Mic, MicOff, Loader, CheckCircle, XCircle, Clock, ChevronRight, Send } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './VoicePanel.css'

const S = { IDLE:'idle', LISTENING:'listening', PROCESSING:'processing',
            PLANNING:'planning', APPROVING:'approving', EXECUTING:'executing',
            DONE:'done', ERROR:'error', SPEAKING:'speaking' }

const SENSITIVE = new Set(['run_terminal','compose_email','delete_file','open_setting'])

export default function VoicePanel() {
  const { transcribe, plan, execute, addLog, backendReady, credits } = useAgent()
  const [step, setStep]         = useState(S.IDLE)
  const [transcript, setTrans]  = useState('')
  const [planData, setPlan]     = useState(null)
  const [execSteps, setExec]    = useState([])
  const [error, setError]       = useState('')
  const [chatText, setChatText] = useState('')
  const [lastOutput, setLastOutput] = useState('')
  const mediaRef  = useRef(null)
  const chunksRef = useRef([])

  /* ── Recording ── */
  const startListening = async () => {
    if (!backendReady) { setError('Backend not ready yet. Please wait.'); return }
    if (credits === 0) { setError('No credits remaining. Buy more at desktoppilot.vercel.app/dashboard'); return }
    setStep(S.LISTENING); setTrans(''); setPlan(null); setExec([]); setError(''); setLastOutput('')
    addLog('Microphone activated', 'info')
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRef.current  = recorder
      chunksRef.current = []
      recorder.ondataavailable = e => chunksRef.current.push(e.data)
      recorder.onstop = () => handleStop(stream)
      recorder.start()
    } catch (e) {
      setError('Microphone access denied.'); setStep(S.ERROR)
      addLog('Mic error: ' + e.message, 'error')
    }
  }

  const stopListening = () => {
    if (mediaRef.current?.state === 'recording') {
      mediaRef.current.stop(); setStep(S.PROCESSING)
    }
  }

  const handleStop = async (stream) => {
    stream.getTracks().forEach(t => t.stop())
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    try {
      setStep(S.PROCESSING)
      addLog('Transcribing via Amazon Transcribe...', 'info')
      const text = await transcribe(blob)
      setTrans(text)
      addLog(`Transcript: "${text}"`, 'success')

      setStep(S.PLANNING)
      addLog('Generating plan via Amazon Bedrock...', 'info')
      const p = await plan(text)
      setPlan(p)
      addLog(`Plan: ${p.tasks?.length} step(s) — ${p.intent}`, 'success')

      if (p.requires_approval) { setStep(S.APPROVING); addLog('Approval required', 'warning') }
      else await runExec(p)
    } catch (e) {
      setError(e.message); setStep(S.ERROR); addLog('Error: ' + e.message, 'error')
    }
  }

  const runExec = async (p) => {
    setStep(S.EXECUTING)
    setExec(p.tasks.map(t => ({ label: taskLabel(t), status: 'pending' })))
    addLog('Executing plan...', 'info')
    try {
      const results = await execute(p)
      results.forEach((r, i) => {
        setExec(prev => prev.map((s, j) =>
          j === i ? { ...s, status: r.success ? 'done' : 'failed' } : s
        ))
        addLog(r.message, r.success ? 'success' : 'error')
      })
      // Show output for commands that produce text results
      const outputResult = results.find(r =>
        r.success && r.message && r.message.length > 30 && (
          r.message.includes('Output:') ||
          r.message.includes('Battery:') ||
          r.message.includes('RAM:') ||
          r.message.includes('Local IP:') ||
          r.message.includes('CPU:') ||
          r.message.includes('Disk') ||
          r.message.includes('Open windows') ||
          r.message.includes('Clipboard:') ||
          r.message.includes('Timer started:') ||
          r.message.includes('Reply') ||
          r.message.includes('Screen text') ||
          r.message.includes('Profile:') ||
          r.message.includes('Copied') ||
          r.message.includes('Code saved')
        )
      )
      if (outputResult) {
        setLastOutput(outputResult.message)
      }
      // Show speaking animation briefly when agent responds with voice
      const hasSpeakTask = p.tasks.some(t => t.tool === 'speak')
      if (hasSpeakTask || results.length > 0) {
        setStep(S.SPEAKING)
        setTimeout(() => setStep(S.DONE), 3000) // Show speaking for 3s
      } else {
        setStep(S.DONE)
      }
      addLog('All steps completed ✓', 'success')
    } catch (e) {
      setStep(S.ERROR); setError(e.message); addLog('Execution failed: ' + e.message, 'error')
    }
  }

  const reset = () => { setStep(S.IDLE); setTrans(''); setPlan(null); setExec([]); setError(''); setChatText(''); setLastOutput('') }

  /* ── Chat input submit (text command instead of voice) ── */
  const handleChatSubmit = async (e) => {
    e.preventDefault()
    const text = chatText.trim()
    if (!text || !backendReady) return
    if (credits === 0) { setError('No credits remaining.'); return }

    setChatText('')
    setTrans(text)
    setStep(S.PLANNING)
    setPlan(null); setExec([]); setError(''); setLastOutput('')
    addLog(`Text command: "${text}"`, 'info')

    try {
      addLog('Generating plan via Amazon Bedrock...', 'info')
      const p = await plan(text)
      setPlan(p)
      addLog(`Plan: ${p.tasks?.length} step(s) — ${p.intent}`, 'success')

      if (p.requires_approval) { setStep(S.APPROVING); addLog('Approval required', 'warning') }
      else await runExec(p)
    } catch (e) {
      setError(e.message); setStep(S.ERROR); addLog('Error: ' + e.message, 'error')
    }
  }

  const isListening  = step === S.LISTENING
  const isBusy       = [S.PROCESSING, S.PLANNING, S.EXECUTING].includes(step)
  const isApproving  = step === S.APPROVING
  const isSpeaking   = step === S.SPEAKING

  return (
    <div className="panel voice-panel">
      <div className="panel-header">
        <span className="panel-title"><Mic size={15} className="panel-title-icon" /> Voice Command</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {credits <= 10 && credits > 0 && (
            <span className="badge badge-yellow text-xs">⚡ {credits} left</span>
          )}
          {credits === 0 && (
            <span className="badge badge-red text-xs">No credits</span>
          )}
          {(step === S.DONE || step === S.ERROR) && (
            <button className="btn btn-ghost text-sm" onClick={reset}>↺ New command</button>
          )}
        </div>
      </div>

      <div className="panel-body voice-body">
        {/* ── Mic button ── */}
        <div className="mic-section">
          <button
            className={`mic-btn ${isListening ? 'mic-listening' : ''} ${isBusy ? 'mic-busy' : ''} ${step === S.DONE ? 'mic-done' : ''} ${step === S.ERROR ? 'mic-error' : ''} ${isSpeaking ? 'mic-speaking' : ''}`}
            onClick={isListening ? stopListening : startListening}
            disabled={isBusy || isApproving || isSpeaking}
          >
            {isBusy
              ? <Loader size={36} className="spin" />
              : isListening
                ? <MicOff size={36} />
                : <Mic size={36} />
            }
            {isListening && <span className="pulse-ring" />}
            {isListening && <span className="pulse-ring pulse-ring-2" />}
            {isSpeaking && <span className="speak-ring" />}
            {isSpeaking && <span className="speak-ring speak-ring-2" />}
            {isSpeaking && <span className="speak-ring speak-ring-3" />}
          </button>

          <p className="mic-hint text-sm text-muted">
            {step === S.IDLE       && (!backendReady ? 'Waiting for backend...' : 'Click to speak')}
            {step === S.LISTENING  && 'Listening — click to stop'}
            {step === S.PROCESSING && 'Transcribing audio...'}
            {step === S.PLANNING   && 'Generating plan with Bedrock...'}
            {step === S.APPROVING  && 'Review the plan below'}
            {step === S.EXECUTING  && 'Executing on your desktop...'}
            {step === S.SPEAKING   && '🔊 Cipher is speaking...'}
            {step === S.DONE       && 'Done! Click to run another command.'}
            {step === S.ERROR      && 'Something went wrong.'}
          </p>
        </div>

        {/* ── Chat input (text command) ── */}
        <div className="chat-input-section">
          <form onSubmit={handleChatSubmit} className="chat-form">
            <input
              className="input chat-input"
              type="text"
              placeholder="Or type a command here..."
              value={chatText}
              onChange={e => setChatText(e.target.value)}
              disabled={isBusy || isApproving}
            />
            <button
              type="submit"
              className="btn btn-primary chat-send-btn"
              disabled={!chatText.trim() || isBusy || isApproving || !backendReady}
            >
              <Send size={13} /> Send
            </button>
          </form>
        </div>

        {/* ── Quick action buttons ── */}
        <div className="quick-actions">
          {[
            { label: '📸 Screenshot', cmd: 'take a screenshot' },
            { label: '💻 System Info', cmd: 'show system info' },
            { label: '🔋 Battery', cmd: 'how much battery' },
            { label: '⏰ Timer 5m', cmd: 'start a 5 minute timer' },
            { label: '📋 Clipboard', cmd: 'what did I copy' },
            { label: '💡 Brightness+', cmd: 'brightness up' },
            { label: '🔊 Volume+', cmd: 'volume up' },
            { label: '✉️ Smart Reply', cmd: 'smart reply to this email' },
          ].map((action, i) => (
            <button
              key={i}
              className="quick-btn"
              onClick={() => { setChatText(action.cmd); }}
              disabled={isBusy}
              title={action.cmd}
            >
              {action.label}
            </button>
          ))}
        </div>

        {/* ── Transcript ── */}
        {transcript && (
          <div className="card transcript-card">
            <p className="section-label">You said</p>
            <p className="transcript-text selectable">"{transcript}"</p>
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div className="card error-card">
            <XCircle size={14} /> <span>{error}</span>
          </div>
        )}

        {/* ── Approval gate ── */}
        {isApproving && planData && (
          <div className="card approval-card">
            <div className="approval-header">
              <span className="badge badge-yellow">⚠ Approval Required</span>
              <p className="text-sm text-muted mt-1">
                This plan includes sensitive actions. Review before proceeding.
              </p>
            </div>
            <div className="approval-tasks">
              {planData.tasks.map((t, i) => (
                <div key={i} className={`approval-task ${SENSITIVE.has(t.tool) ? 'task-sensitive' : 'task-safe'}`}>
                  <ChevronRight size={12} />
                  <span className="text-sm">{taskLabel(t)}</span>
                  {SENSITIVE.has(t.tool) && <span className="badge badge-yellow text-xs">sensitive</span>}
                </div>
              ))}
            </div>
            <div className="approval-actions">
              <button className="btn btn-primary" onClick={() => runExec(planData)}>
                <CheckCircle size={13} /> Approve & Execute
              </button>
              <button className="btn btn-danger" onClick={() => { setStep(S.IDLE); addLog('Plan rejected', 'warning') }}>
                <XCircle size={13} /> Reject
              </button>
            </div>
          </div>
        )}

        {/* ── Execution tracker ── */}
        {execSteps.length > 0 && (
          <div className="card exec-card">
            <p className="section-label">Execution Plan</p>
            <div className="exec-progress">
              <div
                className="exec-progress-fill"
                style={{ width: `${(execSteps.filter(s => s.status === 'done').length / execSteps.length) * 100}%` }}
              />
            </div>
            <ul className="exec-steps">
              {execSteps.map((s, i) => (
                <li key={i} className={`exec-step exec-step--${s.status}`}>
                  <StepIcon status={s.status} />
                  <span className="text-sm">{s.label}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ── Plan preview (before execution) ── */}
        {planData && step === S.APPROVING && (
          <div className="card plan-meta">
            <p className="section-label">Intent</p>
            <p className="text-sm text-muted selectable">{planData.intent}</p>
          </div>
        )}

        {/* ── Output display (code output, system info, etc.) ── */}
        {lastOutput && (
          <div className="card output-card">
            <p className="section-label">Output</p>
            <pre className="output-text selectable">{lastOutput}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

function StepIcon({ status }) {
  if (status === 'done')    return <CheckCircle size={14} className="text-success" />
  if (status === 'failed')  return <XCircle size={14} className="text-danger" />
  if (status === 'running') return <Loader size={14} className="text-accent spin" />
  return <Clock size={14} className="text-muted" />
}

function taskLabel(t) {
  const m = {
    open_application: `Open ${t.name || 'app'}`,
    open_project:     `Open project: ${t.project || ''}`,
    run_terminal:     `Terminal: ${t.command || ''}`,
    wait_for_server:  `Wait for server: ${t.url || ''}`,
    open_browser:     `Browser → ${t.url || ''}`,
    search_web:       `Search: ${t.query || ''}`,
    open_file:        `Open file: ${t.name || ''}`,
    open_setting:     `Settings: ${t.name || ''}`,
    compose_email:    `Email to: ${t.to || ''}`,
  }
  return m[t.tool] || t.tool
}
