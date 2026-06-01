import React, { useState, useEffect } from 'react'
import { Cpu, Minus, Square, X, Maximize2, Wifi, WifiOff } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './TitleBar.css'

export default function TitleBar() {
  const { backendReady, credits, wsConnected } = useAgent()
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    const check = async () => {
      if (window.dp) setMaximized(await window.dp.isMaximized())
    }
    check()
  }, [])

  const handleMaximize = async () => {
    await window.dp?.maximize()
    setMaximized(m => !m)
  }

  return (
    <div className="titlebar">
      {/* Drag region */}
      <div className="titlebar-drag">
        <div className="titlebar-brand">
          <Cpu size={14} className="brand-icon" />
          <span className="brand-name">DesktopPilot</span>
          <span className="brand-tag">AI</span>
        </div>

        <div className="titlebar-center">
          <div className={`backend-pill ${backendReady ? 'pill-ok' : 'pill-starting'}`}>
            <span className="pill-dot" />
            <span>{backendReady ? 'Agent Ready' : 'Starting...'}</span>
          </div>
        </div>

        <div className="titlebar-right">
          <div className={`ws-indicator ${wsConnected ? 'ws-ok' : 'ws-off'}`} title={wsConnected ? 'WebSocket connected' : 'WebSocket disconnected'}>
            {wsConnected ? <Wifi size={11} /> : <WifiOff size={11} />}
          </div>
          <div className="credits-badge">
            <span className="credits-icon">⚡</span>
            <span>{credits} credits</span>
          </div>
        </div>
      </div>

      {/* Window controls — no-drag */}
      <div className="titlebar-controls">
        <button className="wc-btn wc-min"   onClick={() => window.dp?.minimize()}>
          <Minus size={10} />
        </button>
        <button className="wc-btn wc-max"   onClick={handleMaximize}>
          {maximized ? <Square size={9} /> : <Maximize2 size={9} />}
        </button>
        <button className="wc-btn wc-close" onClick={() => window.dp?.close()}>
          <X size={10} />
        </button>
      </div>
    </div>
  )
}
