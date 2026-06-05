import React from 'react'
import { useAgent } from '../context/AgentContext'
import './StatusBar.css'

export default function StatusBar() {
  const { backendReady, agentStatus } = useAgent()

  return (
    <div className="statusbar">
      <div className="statusbar-left">
        <span className={`status-dot ${backendReady ? 'dot-ok' : 'dot-warn'}`} />
        <span className="text-xs text-muted">
          {backendReady ? 'FastAPI :8888' : 'Backend starting...'}
        </span>
      </div>

      <div className="statusbar-right">
        <span className="text-xs text-muted">
          {agentStatus?.platform === 'win32' ? 'Windows' : agentStatus?.platform}
        </span>
        <span className="statusbar-sep" />
        <span className="text-xs text-muted">
          v{agentStatus?.version || '1.0.0'}
        </span>
        <span className="statusbar-sep" />
        <span className="text-xs text-muted">Cipher AI</span>
      </div>
    </div>
  )
}
