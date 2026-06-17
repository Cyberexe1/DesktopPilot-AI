import React from 'react'
import {
  Mic, FolderOpen, GitBranch, Clock,
  Brain, Settings, ExternalLink, Zap,
  Radio, Clipboard, Target
} from 'lucide-react'
import './Sidebar.css'

const NAV_ITEMS = [
  { id: 'voice',     icon: <Mic size={17} />,        label: 'Voice',     shortcut: '⌘1' },
  { id: 'files',     icon: <FolderOpen size={17} />,  label: 'Files',     shortcut: '⌘2' },
  { id: 'projects',  icon: <GitBranch size={17} />,   label: 'Projects',  shortcut: '⌘3' },
  { id: 'activity',  icon: <Clock size={17} />,       label: 'Activity',  shortcut: '⌘4' },
  { id: 'memory',    icon: <Brain size={17} />,       label: 'Memory',    shortcut: '⌘5' },
  { id: 'meeting',   icon: <Radio size={17} />,       label: 'Meeting',   shortcut: '⌘6' },
  { id: 'clipboard', icon: <Clipboard size={17} />,   label: 'Clipboard', shortcut: '⌘7' },
  { id: 'focus',     icon: <Target size={17} />,      label: 'Focus',     shortcut: '⌘8' },
]

const BOTTOM_ITEMS = [
  { id: 'settings', icon: <Settings size={17} />, label: 'Settings' },
]

export default function Sidebar({ active, onNavigate }) {
  return (
    <aside className="sidebar">
      {/* Top nav */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(item => (
          <SidebarItem
            key={item.id}
            item={item}
            isActive={active === item.id}
            onClick={() => onNavigate(item.id)}
          />
        ))}
      </nav>

      <div className="sidebar-spacer" />

      {/* Bottom nav */}
      <nav className="sidebar-nav sidebar-nav-bottom">
        {BOTTOM_ITEMS.map(item => (
          <SidebarItem
            key={item.id}
            item={item}
            isActive={active === item.id}
            onClick={() => onNavigate(item.id)}
          />
        ))}
        <button
          className="sidebar-item sidebar-external"
          data-id="external"
          onClick={() => window.dp?.openExternal('https://desktoppilot.vercel.app/dashboard')}
          title="Open Web Dashboard"
        >
          <span className="sidebar-icon"><ExternalLink size={17} /></span>
          <span className="sidebar-label">Dashboard</span>
        </button>
      </nav>

      {/* Breathing logo mark — only visible when collapsed */}
      <div className="sidebar-logo-mark">
        <Zap size={13} />
      </div>
    </aside>
  )
}

function SidebarItem({ item, isActive, onClick }) {
  return (
    <button
      className={`sidebar-item ${isActive ? 'sidebar-item--active' : ''}`}
      data-id={item.id}
      onClick={onClick}
      title={`${item.label}${item.shortcut ? '  ' + item.shortcut : ''}`}
    >
      <span className="sidebar-icon">{item.icon}</span>
      <span className="sidebar-label">{item.label}</span>
      {isActive && <span className="sidebar-active-bar" />}
    </button>
  )
}
