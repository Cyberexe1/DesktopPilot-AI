import React from 'react'
import { CheckCircle, XCircle, Clock, Loader } from 'lucide-react'
import './ExecutionTracker.css'

const icons = {
  pending: <Clock size={16} className="step-icon pending" />,
  running: <Loader size={16} className="step-icon running spin" />,
  done:    <CheckCircle size={16} className="step-icon done" />,
  failed:  <XCircle size={16} className="step-icon failed" />,
}

export default function ExecutionTracker({ steps }) {
  const completed = steps.filter(s => s.status === 'done').length
  const total     = steps.length
  const progress  = total > 0 ? (completed / total) * 100 : 0

  return (
    <div className="card tracker">
      <div className="tracker-header">
        <span className="card-title text-muted text-sm">Execution Plan</span>
        <span className="text-sm text-muted">{completed}/{total} steps</span>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>

      <ul className="tracker-steps">
        {steps.map((step, i) => (
          <li key={i} className={`tracker-step tracker-step--${step.status}`}>
            {icons[step.status] || icons.pending}
            <span className="step-label">{step.label}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
