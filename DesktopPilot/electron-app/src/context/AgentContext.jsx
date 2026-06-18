import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'

const AgentContext = createContext(null)
const API = 'http://localhost:8888'

export function AgentProvider({ children }) {
  const [backendReady, setBackendReady] = useState(false)
  const [backendLogs,  setBackendLogs]  = useState([])
  const [credits,      setCredits]      = useState(100)
  const [agentStatus,  setAgentStatus]  = useState(null)
  const [wsConnected,  setWsConnected]  = useState(false)
  const wsRef = useRef(null)

  // ── Main process events ──────────────────────────────────────────────────
  useEffect(() => {
    if (!window.dp) return
    window.dp.on('fastapi:status', (data) => setBackendReady(data.running))
    window.dp.on('fastapi:log',    (data) => addLog(data.msg, data.level === 'error' ? 'error' : 'info'))
    window.dp.getStatus().then(setAgentStatus)
    return () => { window.dp.off('fastapi:status'); window.dp.off('fastapi:log') }
  }, [])

  // ── Poll health ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (backendReady) return
    const id = setInterval(async () => {
      try {
        const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2000) })
        if (r.ok) setBackendReady(true)
      } catch {}
    }, 2000)
    return () => clearInterval(id)
  }, [backendReady])

  // ── WebSocket to backend /ws ─────────────────────────────────────────────
  useEffect(() => {
    if (!backendReady) return
    let ws
    let retryTimer

    const connect = () => {
      try {
        ws = new WebSocket('ws://localhost:8888/ws')
        wsRef.current = ws

        ws.onopen = () => {
          setWsConnected(true)
          addLog('WebSocket connected to backend', 'success')
        }
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data)
            if (msg.type === 'plan_ready' && msg.credits_remaining != null) {
              setCredits(msg.credits_remaining)
            }
          } catch {}
        }
        ws.onclose = () => {
          setWsConnected(false)
          retryTimer = setTimeout(connect, 4000)
        }
        ws.onerror = () => setWsConnected(false)
      } catch {}
    }

    connect()
    return () => { clearTimeout(retryTimer); ws?.close() }
  }, [backendReady])

  // ── Fetch credits on ready ───────────────────────────────────────────────
  useEffect(() => {
    if (!backendReady) return
    fetch(`${API}/credits`)
      .then(r => r.json())
      .then(d => { if (d.data?.credits_remaining != null) setCredits(d.data.credits_remaining) })
      .catch(() => {})
  }, [backendReady])

  const addLog = useCallback((msg, type = 'info') => {
    const time = new Date().toLocaleTimeString()
    setBackendLogs(prev => [{ time, msg, type, id: Date.now() + Math.random() }, ...prev].slice(0, 200))
  }, [])

  // ── API helpers ──────────────────────────────────────────────────────────
  const transcribe = useCallback(async (audioBlob) => {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    const res  = await fetch(`${API}/transcribe`, { method: 'POST', body: form })
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    return data.data.text
  }, [])

  const plan = useCallback(async (text) => {
    const res  = await fetch(`${API}/plan`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    const data = await res.json()
    if (res.status === 402) throw new Error(data.detail?.error || 'No credits remaining')
    if (data.error) throw new Error(data.error)
    if (data.data?.credits_remaining != null) setCredits(data.data.credits_remaining)
    return data.data.plan
  }, [])

  const execute = useCallback(async (planData) => {
    const res  = await fetch(`${API}/execute`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: planData }),
    })
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    // Attach speech metadata to the results array so callers can sync animation
    const results = data.data.results
    results.speechMs   = data.data.speech_ms   || 0
    results.spokenText = data.data.spoken_text || ''
    return results
  }, [])

  const getFiles = useCallback(async (query = '') => {
    const res  = await fetch(`${API}/files/search?q=${encodeURIComponent(query)}`)
    const data = await res.json()
    return data.data?.files ?? []
  }, [])

  const reindexFiles = useCallback(async () => {
    const res  = await fetch(`${API}/files/reindex`, { method: 'POST' })
    const data = await res.json()
    return data.data?.indexed ?? 0
  }, [])

  const getProjects = useCallback(async () => {
    const res  = await fetch(`${API}/projects`)
    const data = await res.json()
    return data.data?.projects ?? []
  }, [])

  const addProject = useCallback(async (project) => {
    const res  = await fetch(`${API}/projects`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    })
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    return data.data
  }, [])

  const getMemory = useCallback(async () => {
    const res  = await fetch(`${API}/memory`)
    const data = await res.json()
    return data.data ?? {}
  }, [])

  const getHistory = useCallback(async () => {
    const res  = await fetch(`${API}/memory/commands`)
    const data = await res.json()
    return data.data?.commands ?? []
  }, [])

  return (
    <AgentContext.Provider value={{
      backendReady, backendLogs, addLog,
      credits, setCredits, agentStatus, wsConnected,
      transcribe, plan, execute,
      getFiles, reindexFiles,
      getProjects, addProject,
      getMemory, getHistory,
    }}>
      {children}
    </AgentContext.Provider>
  )
}

export const useAgent = () => {
  const ctx = useContext(AgentContext)
  if (!ctx) throw new Error('useAgent must be used inside AgentProvider')
  return ctx
}
