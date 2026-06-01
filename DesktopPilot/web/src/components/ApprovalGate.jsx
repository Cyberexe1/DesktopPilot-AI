import React from 'react'
import { ShieldAlert, Check, X } from 'lucide-react'
import './ApprovalGate.css'

const SENSITIVE_LABELS = {
  run_terminal:  '⚡ Terminal command',
  compose_email: '📧 Send email',
  delete_file:   '🗑 Delete file',
  open_setting:  '⚙ System setting',
}

export default function ApprovalGate({ plan, onApprove, onReject }) {
  const sensitiveTasks = plan.tasks.filter(t => SENSITIVE_LABELS[t.tool])
  const safeTasks      = plan.tasks.filter(t => !SENSITIVE_LABELS[t.tool])

  return (
    <div className="card approval-gate">
      <div className="approval-header">
        <ShieldAlert size={20} className="approval-icon" />
        <div>
          <h3>Approval Required</h3>
          <p className="text-muted text-sm">
            This plan includes sensitive actions. Review before proceeding.
          </p>
        </div>
      </div>

      {sensitiveTasks.length > 0 && (
        <div className="approval-section">
          <p className="section-label text-sm">Requires approval:</p>
          <ul className="task-list task-list--sensitive">
            {sensitiveTasks.map((t, i) => (
              <li key={i}>
                <span className="task-type">{SENSITIVE_LABELS[t.tool]}</span>
                <span className="task-detail text-muted text-sm">
                  {t.command || t.to || t.name || t.url || ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {safeTasks.length > 0 && (
        <div className="approval-section">
          <p className="section-label text-sm">Will also run automatically:</p>
          <ul className="task-list task-list--safe">
            {safeTasks.map((t, i) => (
              <li key={i} className="text-muted text-sm">
                ✓ {t.tool.replace(/_/g, ' ')} {t.name || t.url || t.project || ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="approval-actions">
        <button className="btn-approve" onClick={onApprove}>
          <Check size={16} /> Approve & Execute
        </button>
        <button className="btn-reject" onClick={onReject}>
          <X size={16} /> Reject
        </button>
      </div>
    </div>
  )
}
