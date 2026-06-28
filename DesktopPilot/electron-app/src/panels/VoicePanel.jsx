import React, { useState, useRef, useEffect } from 'react'
import { Mic, MicOff, Loader, CheckCircle, XCircle, Clock, ChevronRight, Send, Radio } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './VoicePanel.css'

const S = {
  IDLE:'idle', LISTENING:'listening', PROCESSING:'processing',
  PLANNING:'planning', APPROVING:'approving', EXECUTING:'executing',
  DONE:'done', ERROR:'error', SPEAKING:'speaking'
}

const SENSITIVE = new Set(['run_terminal','compose_email','delete_file','open_setting'])
const WAKE_WORDS = ['hey cipher', 'hi cipher', 'hello cipher', 'okay cipher', 'cipher']

// ── Voice activity detection (auto-send on silence) ──
const VAD_SILENCE_MS   = 2000   // stop after this much trailing silence
const VAD_THRESHOLD    = 0.015  // RMS volume (0..1) above which counts as speech
const VAD_MAX_MS       = 25000  // hard cap on recording length
const VAD_NO_SPEECH_MS = 8000   // stop if no speech ever detected

// ── Instant acknowledgment (spoken client-side, zero latency) ──
const ACK_PHRASES = ['On it.', 'Got it.', 'Sure.', 'Right away.', 'Working on it.']
let _ackIdx = 0
function speakAck() {
  try {
    const synth = window.speechSynthesis
    if (!synth) return
    const u = new SpeechSynthesisUtterance(ACK_PHRASES[_ackIdx++ % ACK_PHRASES.length])
    u.rate = 1.05
    synth.cancel()
    synth.speak(u)
  } catch {}
}

// Typewriter hook — reveals text char by char
function useTypewriter(text, speed = 22) {
  const [displayed, setDisplayed] = useState('')
  useEffect(() => {
    if (!text) { setDisplayed(''); return }
    setDisplayed('')
    let i = 0
    const timer = setInterval(() => {
      i++
      setDisplayed(text.slice(0, i))
      if (i >= text.length) clearInterval(timer)
    }, speed)
    return () => clearInterval(timer)
  }, [text, speed])
  return displayed
}

export default function VoicePanel() {
  const { transcribe, plan, execute, addLog, backendReady, credits, greeting } = useAgent()
  const [step, setStep]         = useState(S.IDLE)
  const [transcript, setTrans]  = useState('')
  const [planData, setPlan]     = useState(null)
  const [execSteps, setExec]    = useState([])
  const [error, setError]       = useState('')
  const [chatText, setChatText] = useState('')
  const [lastOutput, setLastOutput] = useState('')
  const [wakeMode, setWakeMode] = useState(false)
  const [wakeListening, setWakeListening] = useState(false)
  const mediaRef      = useRef(null)
  const chunksRef     = useRef([])
  const wakeRef       = useRef(null)
  const wakeChunksRef = useRef([])
  const audioCtxRef   = useRef(null)
  const vadRafRef     = useRef(null)
  const stepRef       = useRef(S.IDLE)

  const typedTranscript = useTypewriter(transcript, 20)

  useEffect(() => { stepRef.current = step }, [step])

  // ── Greeting: play the speaking wave animation while the agent greets ────
  // AgentContext fires the greeting on app open/refresh and publishes
  // { text, ms, id }. We mirror it as a SPEAKING step so the orb animates.
  useEffect(() => {
    if (!greeting?.id) return
    if (stepRef.current !== S.IDLE) return   // don't interrupt an active command
    setStep(S.SPEAKING)
    setLastOutput('')
    const t = setTimeout(() => {
      // Only return to idle if we're still showing the greeting animation
      setStep(prev => (prev === S.SPEAKING ? S.IDLE : prev))
    }, greeting.ms)
    return () => clearTimeout(t)
  }, [greeting?.id]) // eslint-disable-line

  // Listen for wake word detected from the Electron main process (optional
  // local listener). The primary wake word is the in-app browser listener below.
  useEffect(() => {
    if (!window.dp) return
    const handleWake = () => {
      if (stepRef.current === S.IDLE && backendReady) {
        addLog('Wake word detected — activating', 'success')
        startListening()
      }
    }
    window.dp.on('wake:detected', handleWake)
    return () => window.dp.off('wake:detected')
  }, [backendReady]) // eslint-disable-line

  /* ── Wake Word ── */
  useEffect(() => {
    if (!wakeMode || !backendReady) return
    let active = true

    const listenForWake = async () => {
      if (!active || stepRef.current !== S.IDLE) {
        if (active) setTimeout(listenForWake, 1000)
        return
      }
      setWakeListening(true)
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
        wakeRef.current = recorder
        wakeChunksRef.current = []
        recorder.ondataavailable = e => wakeChunksRef.current.push(e.data)
        recorder.onstop = async () => {
          stream.getTracks().forEach(t => t.stop())
          setWakeListening(false)
          if (!active) return
          const blob = new Blob(wakeChunksRef.current, { type: 'audio/webm' })
          try {
            const text = await transcribe(blob)
            const lower = text.toLowerCase().trim()
            const hasWake = WAKE_WORDS.some(w => lower.includes(w))
            if (hasWake) {
              let command = lower
              for (const w of WAKE_WORDS) command = command.replace(w, '').trim()
              if (command.length > 2) {
                addLog(`Wake word detected! Command: "${command}"`, 'success')
                setTrans(command)
                setStep(S.PLANNING)
                const p = await plan(command)
                setPlan(p)
                addLog(`Plan: ${p.tasks?.length} step(s) — ${p.intent}`, 'success')
                if (p.requires_approval) setStep(S.APPROVING)
                else await runExec(p)
              } else {
                addLog('Wake word detected! Listening...', 'success')
                startListening()
              }
            } else {
              if (active) setTimeout(listenForWake, 300)
            }
          } catch {
            if (active) setTimeout(listenForWake, 1000)
          }
        }
        recorder.start()
        setTimeout(() => { if (recorder.state === 'recording') recorder.stop() }, 3000)
      } catch {
        setWakeListening(false)
        if (active) setTimeout(listenForWake, 2000)
      }
    }

    listenForWake()
    return () => {
      active = false
      setWakeListening(false)
      try { if (wakeRef.current?.state === 'recording') wakeRef.current.stop() } catch {}
    }
  }, [wakeMode, backendReady]) // eslint-disable-line

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
      _startVAD(stream)   // auto-stop on 2s of silence
    } catch (e) {
      setError('Microphone access denied.'); setStep(S.ERROR)
      addLog('Mic error: ' + e.message, 'error')
    }
  }

  // Monitor mic volume and auto-stop after VAD_SILENCE_MS of silence
  // (once speech has started), or at the max/no-speech caps.
  const _startVAD = (stream) => {
    let ctx
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)()
    } catch {
      return // Web Audio unavailable — fall back to manual stop only
    }
    audioCtxRef.current = ctx
    const source   = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)
    const buf = new Uint8Array(analyser.fftSize)

    const startedAt = performance.now()
    let speechStartedAt = 0
    let lastLoudAt = startedAt

    const tick = () => {
      if (!mediaRef.current || mediaRef.current.state !== 'recording') return
      analyser.getByteTimeDomainData(buf)
      let sum = 0
      for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v }
      const rms = Math.sqrt(sum / buf.length)
      const now = performance.now()

      if (rms >= VAD_THRESHOLD) {
        lastLoudAt = now
        if (!speechStartedAt) speechStartedAt = now
      }

      const silenceFor = now - lastLoudAt
      const elapsed    = now - startedAt

      const shouldStop =
        (speechStartedAt && silenceFor >= VAD_SILENCE_MS) ||  // spoke then went quiet
        (!speechStartedAt && elapsed >= VAD_NO_SPEECH_MS) ||  // never spoke
        (elapsed >= VAD_MAX_MS)                               // hard cap

      if (shouldStop) { stopListening(); return }
      vadRafRef.current = requestAnimationFrame(tick)
    }
    vadRafRef.current = requestAnimationFrame(tick)
  }

  const _stopVAD = () => {
    if (vadRafRef.current) { cancelAnimationFrame(vadRafRef.current); vadRafRef.current = null }
    if (audioCtxRef.current) { try { audioCtxRef.current.close() } catch {} audioCtxRef.current = null }
  }

  const stopListening = () => {
    _stopVAD()
    if (mediaRef.current?.state === 'recording') {
      mediaRef.current.stop(); setStep(S.PROCESSING)
    }
  }

  const handleStop = async (stream) => {
    _stopVAD()
    stream.getTracks().forEach(t => t.stop())
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
    try {
      setStep(S.PROCESSING)
      addLog('Transcribing via Amazon Transcribe...', 'info')
      const text = await transcribe(blob)
      if (!text || !text.trim()) {
        addLog('No speech detected', 'warning')
        setStep(S.IDLE)
        return
      }
      setTrans(text)
      speakAck()   // instant spoken "On it" while the plan is generated
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
    const steps = p.tasks.map(t => ({ label: taskLabel(t), status: 'pending' }))
    setExec(steps)
    addLog('Executing plan...', 'info')
    try {
      const results = await execute(p)
      for (let i = 0; i < results.length; i++) {
        setExec(prev => prev.map((s, j) => j === i ? { ...s, status: 'running' } : s))
        await new Promise(r => setTimeout(r, 100))
        setExec(prev => prev.map((s, j) =>
          j === i
            ? { ...s,
                status: results[i].success ? 'done' : 'failed',
                label: results[i].message?.startsWith('[Alternative]') ? `↪ ${prev[j].label}` : prev[j].label
              }
            : s
        ))
        addLog(results[i].message, results[i].success ? 'success' : 'error')
      }
      const outputResult = results.find(r =>
        r.success && r.message && r.message.length > 30 && (
          r.message.includes('Output:') || r.message.includes('Battery:') ||
          r.message.includes('RAM:')    || r.message.includes('Local IP:') ||
          r.message.includes('CPU:')    || r.message.includes('Disk') ||
          r.message.includes('Open windows') || r.message.includes('Clipboard:') ||
          r.message.includes('Timer started:') || r.message.includes('Reply') ||
          r.message.includes('Screen text') || r.message.includes('Profile:') ||
          r.message.includes('Copied') || r.message.includes('Code saved')
        )
      )
      if (outputResult) setLastOutput(outputResult.message)
      const hasSpeakTask = p.tasks.some(t => t.tool === 'speak' || t.tool === 'answer_question')
      if (hasSpeakTask || results.length > 0) {
        setStep(S.SPEAKING)
        // Animate the waveform for the full duration of the actual speech.
        let speakDuration
        if (results.speechMs && results.speechMs > 0) {
          // Backend told us exactly how long the speech is
          speakDuration = results.speechMs + 400
        } else {
          // Fallback: estimate from the longest spoken result message
          // (~2.75 words/sec speaking rate)
          const spokenMsg = results.reduce(
            (longest, r) => (r.message && r.message.length > longest.length ? r.message : longest),
            ''
          )
          const words = spokenMsg.trim() ? spokenMsg.trim().split(/\s+/).length : 0
          speakDuration = words > 0
            ? Math.min(Math.max((words / 2.75) * 1000 + 600, 2000), 20000)
            : 3000
        }
        setTimeout(() => setStep(S.DONE), speakDuration)
      } else {
        setStep(S.DONE)
      }
      addLog('All steps completed ✓', 'success')
    } catch (e) {
      setStep(S.ERROR); setError(e.message); addLog('Execution failed: ' + e.message, 'error')
    }
  }

  const reset = () => {
    setStep(S.IDLE); setTrans(''); setPlan(null)
    setExec([]); setError(''); setChatText(''); setLastOutput('')
  }

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

  const isListening = step === S.LISTENING
  const isBusy      = [S.PROCESSING, S.PLANNING, S.EXECUTING].includes(step)
  const isApproving = step === S.APPROVING
  const isSpeaking  = step === S.SPEAKING

  const micClass = [
    'mic-btn',
    isListening          ? 'mic-listening' : '',
    isBusy               ? 'mic-busy'      : '',
    step === S.DONE      ? 'mic-done'      : '',
    step === S.ERROR     ? 'mic-error'     : '',
    isSpeaking           ? 'mic-speaking'  : '',
  ].filter(Boolean).join(' ')

  const hintText = {
    [S.IDLE]:       !backendReady ? 'Waiting for backend...' : wakeMode ? 'Say "Hey Cipher" to activate' : 'Click to speak',
    [S.LISTENING]:  'Listening — click to stop',
    [S.PROCESSING]: 'Transcribing audio...',
    [S.PLANNING]:   'Generating plan with Bedrock...',
    [S.APPROVING]:  'Review the plan below',
    [S.EXECUTING]:  'Executing on your desktop...',
    [S.SPEAKING]:   'Cipher is responding...',
    [S.DONE]:       'Done! Click to run another command.',
    [S.ERROR]:      'Something went wrong.',
  }[step] || ''

  return (
    <div className="panel voice-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Mic size={15} className="panel-title-icon" /> Voice Command
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            className={`btn btn-ghost text-xs ${wakeMode ? 'wake-indicator--active' : ''}`}
            onClick={() => setWakeMode(w => !w)}
            title={wakeMode ? 'Wake word active — say "Hey Cipher"' : 'Enable wake word'}
          >
            <Radio size={12} /> {wakeMode ? 'Listening' : 'Wake Word'}
          </button>
          {credits <= 10 && credits > 0 && (
            <span className="badge badge-yellow text-xs">⚡ {credits} left</span>
          )}
          {credits === 0 && (
            <span className="badge badge-red text-xs">No credits</span>
          )}
          {(step === S.DONE || step === S.ERROR) && (
            <button className="btn btn-ghost text-sm" onClick={reset}>↺ New</button>
          )}
        </div>
      </div>

      <div className="panel-body voice-body">

        {/* ── Mic orb ── */}
        <div className="mic-section">
          <div className="mic-orb-wrap">
            <button
              className={micClass}
              onClick={isListening ? stopListening : startListening}
              disabled={isBusy || isApproving || isSpeaking}
            >
              {/* inner content */}
              {isBusy ? (
                <Loader size={60} className="spin" />
              ) : isSpeaking ? (
                <div className="wave-bars">
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                  <span className="wave-bar" />
                </div>
              ) : isListening ? (
                <MicOff size={60} />
              ) : (
                <Mic size={60} />
              )}

              {/* rings */}
              {isListening && <span className="pulse-ring" />}
              {isListening && <span className="pulse-ring pulse-ring-2" />}
              {isListening && <span className="pulse-ring pulse-ring-3" />}
              {isSpeaking  && <span className="speak-ring" />}
              {isSpeaking  && <span className="speak-ring speak-ring-2" />}
              {isSpeaking  && <span className="speak-ring speak-ring-3" />}
            </button>
          </div>

          <p className="mic-hint">{hintText}</p>

          {wakeMode && step === S.IDLE && (
            <div className={`wake-indicator ${wakeListening ? 'wake-indicator--active' : ''}`}>
              <span className="wake-dot" />
              <span>{wakeListening ? 'Listening for "Hey Cipher"...' : 'Wake word active'}</span>
            </div>
          )}
        </div>

        {/* ── Chat input ── */}
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

        {/* ── Quick actions ── */}
        <div className="quick-actions">
          {[
            { label: '📸 Screenshot',  cmd: 'take a screenshot' },
            { label: '💻 System Info', cmd: 'show system info' },
            { label: '🔋 Battery',     cmd: 'how much battery' },
            { label: '⏰ Timer 5m',    cmd: 'start a 5 minute timer' },
            { label: '📋 Clipboard',   cmd: 'what did I copy' },
            { label: '💡 Brightness+', cmd: 'brightness up' },
            { label: '🔊 Volume+',     cmd: 'volume up' },
            { label: '✉️ Smart Reply', cmd: 'smart reply to this email' },
          ].map((action, i) => (
            <button
              key={i}
              className="quick-btn"
              onClick={() => setChatText(action.cmd)}
              disabled={isBusy}
              title={action.cmd}
            >
              {action.label}
            </button>
          ))}
        </div>

        {/* ── Transcript (typewriter) ── */}
        {transcript.trim() && (
          <div className="card transcript-card">
            <p className="section-label">You said</p>
            <p className="transcript-text selectable">"{typedTranscript}"</p>
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div className="card error-card">
            <XCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* ── Approval gate ── */}
        {isApproving && planData && (
          <div className="card approval-card card--glow-warning">
            <div className="approval-header">
              <span className="badge badge-yellow">⚠ Approval Required</span>
              <p className="text-sm text-2 mt-1">
                This plan includes sensitive actions. Review before proceeding.
              </p>
            </div>
            <div className="approval-tasks">
              {planData.tasks.map((t, i) => (
                <div key={i} className={`approval-task ${SENSITIVE.has(t.tool) ? 'task-sensitive' : 'task-safe'}`}>
                  <ChevronRight size={12} />
                  <span className="text-sm">{taskLabel(t)}</span>
                  {SENSITIVE.has(t.tool) && (
                    <span className="badge badge-yellow text-xs">sensitive</span>
                  )}
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

        {/* ── Plan intent ── */}
        {planData && step === S.APPROVING && planData.intent?.trim() && (
          <div className="card plan-meta">
            <p className="section-label">Intent</p>
            <p className="text-sm text-2 selectable">{planData.intent}</p>
          </div>
        )}

        {/* ── Output ── */}
        {lastOutput && (
          <div className="card output-card card--glow-accent">
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
  if (status === 'failed')  return <XCircle     size={14} className="text-danger"  />
  if (status === 'running') return <Loader      size={14} className="text-accent spin" />
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
  // Fall back to a human-readable version of the tool name so a step is
  // never rendered as a blank row (e.g. "take_screenshot" → "Take screenshot").
  if (m[t.tool]) return m[t.tool]
  if (t.tool) {
    const words = t.tool.replace(/_/g, ' ').trim()
    return words.charAt(0).toUpperCase() + words.slice(1)
  }
  return 'Step'
}
