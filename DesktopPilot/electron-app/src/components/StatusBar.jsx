import React from 'react'
import { useAgent } from '../context/AgentContext'
import './StatusBar.css'

export default function StatusBar() {
  const { backendReady, agentStatus } = useAgent()

  return (
    <div className="statusbar">
      <div className="statusbar-left">
        <div className={`status-dot-wrap ${backendReady ? 'ping-ok' : ''}`}>
          <span className={`status-dot ${backendReady ? 'dot-ok' : 'dot-warn'}`} />
        </div>
        <span className={`statusbar-text ${backendReady ? 'statusbar-text--ready' : ''}`}>
          {backendReady ? 'FastAPI :8888' : 'Backend starting...'}
        </span>
      </div>

      <div className="statusbar-right">
        <span className="statusbar-text">
          {agentStatus?.platform === 'win32' ? 'Windows' : (agentStatus?.platform || 'Windows')}
        </span>
        <span className="statusbar-sep" />
        <span className="statusbar-text">
          v{agentStatus?.version || '1.0.1'}
        </span>
        <span className="statusbar-sep" />
        <span className="statusbar-text">DesktopPilot AI</span>
      </div>
    </div>
  )
}
