import React, { useState, useEffect } from 'react'
import { Clock, RefreshCw, Trash2, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './ActivityPanel.css'

export default function ActivityPanel() {
  const { getHistory, backendLogs, addLog } = useAgent()
  const [history,  setHistory]  = useState([])
  const [tab,      setTab]      = useState('commands')  // 'commands' | 'logs'
  const [loading,  setLoading]  = useState(false)

  const load = async () => {
    setLoading(true)
    try { setHistory(await getHistory()) }
    catch (e) { addLog(e.message, 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="panel activity-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Clock size={15} className="panel-title-icon" /> Activity
        </span>
        <button className="btn-icon" onClick={load} title="Refresh">
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {/* Tabs */}
      <div className="activity-tabs">
        <button className={`tab-btn ${tab === 'commands' ? 'tab-active' : ''}`} onClick={() => setTab('commands')}>
          Commands ({history.length})
        </button>
        <button className={`tab-btn ${tab === 'logs' ? 'tab-active' : ''}`} onClick={() => setTab('logs')}>
          Backend Logs ({backendLogs.length})
        </button>
      </div>

      <div className="panel-body activity-body">
        {tab === 'commands' && (
          <>
            {history.length === 0 && (
              <div className="empty-state">
                <Clock size={28} className="empty-state-icon" />
                <p className="text-sm">No commands yet</p>
                <p className="text-xs text-muted">Your voice command history will appear here</p>
              </div>
            )}
            <ul className="history-list">
              {history.map((h, i) => (
                <li key={i} className="history-item">
                  <div className="history-icon">
                    <CheckCircle size={13} className="text-success" />
                  </div>
                  <div className="history-content">
                    <p className="history-cmd selectable">{h.command}</p>
                    <p className="history-time text-xs text-muted">{h.timestamp}</p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}

        {tab === 'logs' && (
          <>
            {backendLogs.length === 0 && (
              <div className="empty-state">
                <AlertCircle size={28} className="empty-state-icon" />
                <p className="text-sm">No logs yet</p>
              </div>
            )}
            <ul className="log-list">
              {backendLogs.map((l) => (
                <li key={l.id} className={`log-item log-item--${l.type}`}>
                  <span className="log-time font-mono text-xs text-muted">{l.time}</span>
                  <span className="log-msg text-xs selectable">{l.msg}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}
