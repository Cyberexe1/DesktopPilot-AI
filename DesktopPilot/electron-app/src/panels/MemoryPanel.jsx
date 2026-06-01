import React, { useState, useEffect } from 'react'
import { Brain, RefreshCw, GitBranch, Clock, Zap } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './MemoryPanel.css'

export default function MemoryPanel() {
  const { getMemory, addLog } = useAgent()
  const [memory,  setMemory]  = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try { setMemory(await getMemory()) }
    catch (e) { addLog(e.message, 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="panel memory-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Brain size={15} className="panel-title-icon" /> Memory & Context
        </span>
        <button className="btn-icon" onClick={load} title="Refresh">
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="panel-body">
        <p className="text-xs text-muted" style={{ marginBottom: '1rem' }}>
          DesktopPilot remembers your recent activity to resolve ambiguous commands like "open my project".
        </p>

        {/* Last project */}
        <div className="card memory-card">
          <div className="memory-card-header">
            <GitBranch size={14} className="text-accent" />
            <span className="section-label" style={{ margin: 0 }}>Last Project</span>
          </div>
          {memory?.last_project ? (
            <div className="memory-value">
              <p className="memory-name">{memory.last_project.name}</p>
              <p className="text-xs text-muted font-mono">{memory.last_project.path}</p>
              {memory.last_project.framework && (
                <span className="badge badge-blue text-xs" style={{ marginTop: '0.35rem' }}>
                  {memory.last_project.framework}
                </span>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted" style={{ marginTop: '0.5rem' }}>No project used yet</p>
          )}
        </div>

        {/* Recent commands */}
        <div className="card memory-card">
          <div className="memory-card-header">
            <Clock size={14} className="text-accent" />
            <span className="section-label" style={{ margin: 0 }}>Recent Commands</span>
          </div>
          {memory?.recent_commands?.length > 0 ? (
            <ul className="recent-list">
              {memory.recent_commands.map((cmd, i) => (
                <li key={i} className="recent-item">
                  <Zap size={11} className="text-muted" />
                  <span className="text-sm selectable">{cmd}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted" style={{ marginTop: '0.5rem' }}>No recent commands</p>
          )}
        </div>

        {/* How memory works */}
        <div className="card memory-info">
          <p className="section-label">How it works</p>
          <ul className="info-list">
            {[
              'When you say "open my project", the AI checks your last used project.',
              'Recent commands are stored locally in SQLite.',
              'In Phase 3, memory syncs to Amazon DynamoDB across sessions.',
              'Memory enriches every Bedrock prompt for smarter responses.',
            ].map((line, i) => (
              <li key={i} className="text-xs text-muted">{line}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
