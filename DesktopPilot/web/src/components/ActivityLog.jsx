import React from 'react'
import './ActivityLog.css'

const typeClass = {
  info:    'log-info',
  success: 'log-success',
  warning: 'log-warning',
  error:   'log-error',
}

const typeIcon = {
  info:    '○',
  success: '✓',
  warning: '⚠',
  error:   '✗',
}

export default function ActivityLog({ logs }) {
  return (
    <div className="card activity-log">
      <div className="log-header">
        <span className="card-title text-muted text-sm">Activity Log</span>
        {logs.length > 0 && (
          <span className="badge badge-info">{logs.length}</span>
        )}
      </div>

      {logs.length === 0 ? (
        <p className="log-empty text-muted text-sm">
          No activity yet. Start a voice command to see logs here.
        </p>
      ) : (
        <ul className="log-list">
          {logs.map((log, i) => (
            <li key={i} className={`log-item ${typeClass[log.type] || 'log-info'}`}>
              <span className="log-icon">{typeIcon[log.type] || '○'}</span>
              <span className="log-msg">{log.msg}</span>
              <span className="log-time text-muted text-sm">{log.time}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
