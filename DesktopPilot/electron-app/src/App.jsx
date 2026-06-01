import React, { useState, useEffect } from 'react'
import TitleBar       from './components/TitleBar'
import Sidebar        from './components/Sidebar'
import VoicePanel     from './panels/VoicePanel'
import FilesPanel     from './panels/FilesPanel'
import ProjectsPanel  from './panels/ProjectsPanel'
import ActivityPanel  from './panels/ActivityPanel'
import MemoryPanel    from './panels/MemoryPanel'
import SettingsPanel  from './panels/SettingsPanel'
import StatusBar      from './components/StatusBar'
import { AgentProvider, useAgent } from './context/AgentContext'
import './styles/app.css'

const PANELS = {
  voice:    <VoicePanel />,
  files:    <FilesPanel />,
  projects: <ProjectsPanel />,
  activity: <ActivityPanel />,
  memory:   <MemoryPanel />,
  settings: <SettingsPanel />,
}

function AppShell() {
  const [activePanel, setActivePanel] = useState('voice')
  const { backendReady } = useAgent()

  return (
    <div className="app-shell">
      <TitleBar />
      <div className="app-body">
        <Sidebar active={activePanel} onNavigate={setActivePanel} />
        <main className="app-main">
          {PANELS[activePanel]}
        </main>
      </div>
      <StatusBar />
    </div>
  )
}

export default function App() {
  return (
    <AgentProvider>
      <AppShell />
    </AgentProvider>
  )
}
