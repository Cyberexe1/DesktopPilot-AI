import React, { useState, useEffect } from 'react'
import TitleBar       from './components/TitleBar'
import Sidebar        from './components/Sidebar'
import VoicePanel     from './panels/VoicePanel'
import FilesPanel     from './panels/FilesPanel'
import ProjectsPanel  from './panels/ProjectsPanel'
import ActivityPanel  from './panels/ActivityPanel'
import MemoryPanel    from './panels/MemoryPanel'
import SettingsPanel  from './panels/SettingsPanel'
import MeetingPanel   from './panels/MeetingPanel'
import ClipboardPanel from './panels/ClipboardPanel'
import FocusPanel     from './panels/FocusPanel'
import LoginPanel     from './panels/LoginPanel'
import StatusBar      from './components/StatusBar'
import { AgentProvider } from './context/AgentContext'
import './styles/app.css'

const PANEL_MAP = {
  voice:     VoicePanel,
  files:     FilesPanel,
  projects:  ProjectsPanel,
  activity:  ActivityPanel,
  memory:    MemoryPanel,
  settings:  SettingsPanel,
  meeting:   MeetingPanel,
  clipboard: ClipboardPanel,
  focus:     FocusPanel,
}

function AppBackground() {
  return (
    <div className="app-bg" aria-hidden="true">
      {/* animated grid */}
      <div className="app-bg__grid" />
      {/* radial red glow centre */}
      <div className="app-bg__glow app-bg__glow--center" />
      {/* corner accent glows */}
      <div className="app-bg__glow app-bg__glow--tl" />
      <div className="app-bg__glow app-bg__glow--br" />
      {/* floating particles */}
      {Array.from({ length: 18 }).map((_, i) => (
        <span key={i} className="app-bg__particle" style={{ '--i': i }} />
      ))}
      {/* horizontal scan line */}
      <div className="app-bg__scan" />
    </div>
  )
}

function AppShell() {
  const [activePanel, setActivePanel] = useState('voice')
  const [panelKey, setPanelKey] = useState('voice-0')

  const handleNavigate = (id) => {
    if (id === activePanel) return
    setActivePanel(id)
    setPanelKey(`${id}-${Date.now()}`)
  }

  const PanelComponent = PANEL_MAP[activePanel] || VoicePanel

  return (
    <div className="app-shell">
      <AppBackground />
      <TitleBar />
      <div className="app-body">
        <Sidebar active={activePanel} onNavigate={handleNavigate} />
        <main className="app-main">
          <div key={panelKey} className="panel-enter">
            <PanelComponent />
          </div>
        </main>
      </div>
      <StatusBar />
    </div>
  )
}

export default function App() {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const saved = localStorage.getItem('cipher_electron_user')
    if (saved) {
      try { setUser(JSON.parse(saved)) } catch {}
    }
    setLoading(false)
  }, [])

  const handleLogin  = (userData) => {
    setUser(userData)
    localStorage.setItem('cipher_electron_user', JSON.stringify(userData))
  }

  const handleLogout = () => {
    setUser(null)
    localStorage.removeItem('cipher_electron_user')
  }

  if (loading) return null

  if (!user) {
    return <LoginPanel onLogin={handleLogin} />
  }

  return (
    <AgentProvider user={user} onLogout={handleLogout}>
      <AppShell />
    </AgentProvider>
  )
}
