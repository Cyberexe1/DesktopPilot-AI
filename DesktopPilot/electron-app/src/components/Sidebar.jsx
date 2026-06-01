import React from 'react'
import {
  Mic, FolderOpen, GitBranch, Clock,
  Brain, Settings, ExternalLink, Cpu
} from 'lucide-react'
import './Sidebar.css'

const NAV_ITEMS = [
  { id: 'voice',    icon: <Mic size={18} />,        label: 'Voice',    shortcut: '⌘1' },
  { id: 'files',    icon: <FolderOpen size={18} />,  label: 'Files',    shortcut: '⌘2' },
  { id: 'projects', icon: <GitBranch size={18} />,   label: 'Projects', shortcut: '⌘3' },
  { id: 'activity', icon: <Clock size={18} />,       label: 'Activity', shortcut: '⌘4' },
  { id: 'memory',   icon: <Brain size={18} />,       label: 'Memory',   shortcut: '⌘5' },
]

const BOTTOM_ITEMS = [
  { id: 'settings', icon: <Settings size={18} />, label: 'Settings' },
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

      {/* Spacer */}
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
          onClick={() => window.dp?.openExternal('https://desktoppilot.vercel.app/dashboard')}
          title="Open Web Dashboard"
        >
          <span className="sidebar-icon"><ExternalLink size={18} /></span>
          <span className="sidebar-label">Dashboard</span>
        </button>
      </nav>
    </aside>
  )
}

function SidebarItem({ item, isActive, onClick }) {
  return (
    <button
      className={`sidebar-item ${isActive ? 'sidebar-item--active' : ''}`}
      onClick={onClick}
      title={`${item.label} ${item.shortcut || ''}`}
    >
      <span className="sidebar-icon">{item.icon}</span>
      <span className="sidebar-label">{item.label}</span>
      {isActive && <span className="sidebar-active-bar" />}
    </button>
  )
}
