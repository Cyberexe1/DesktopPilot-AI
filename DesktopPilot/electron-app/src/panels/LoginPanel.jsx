import React, { useState } from 'react'
import { LogIn, UserPlus, Eye, EyeOff } from 'lucide-react'
import './LoginPanel.css'

const API = 'http://localhost:8000'

export default function LoginPanel({ onLogin }) {
  const [mode, setMode]         = useState('login')
  const [name, setName]         = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const endpoint = mode === 'signup' ? '/auth/signup' : '/auth/login'
      const body = mode === 'signup'
        ? { name, email, password }
        : { email, password }

      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (res.ok && data.data?.success) {
        onLogin(data.data.user)
      } else {
        setError(data.detail?.error || data.data?.error || 'Authentication failed')
      }
    } catch (e) {
      setError('Cannot connect to backend. Make sure the agent is running.')
    }

    setLoading(false)
  }

  return (
    <div className="login-panel">
      <div className="login-panel-card">
        <h1 className="login-panel-brand">Cipher AI</h1>
        <p className="login-panel-sub">
          {mode === 'login' ? 'Sign in to continue' : 'Create your account'}
        </p>

        <div className="lp-tabs">
          <button className={`lp-tab ${mode === 'login' ? 'lp-tab-active' : ''}`}
            onClick={() => { setMode('login'); setError('') }}>
            Sign In
          </button>
          <button className={`lp-tab ${mode === 'signup' ? 'lp-tab-active' : ''}`}
            onClick={() => { setMode('signup'); setError('') }}>
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="lp-form">
          {mode === 'signup' && (
            <input
              className="lp-input"
              type="text"
              placeholder="Full Name"
              value={name}
              onChange={e => setName(e.target.value)}
              required
            />
          )}
          <input
            className="lp-input"
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
          <div className="lp-pw-wrap">
            <input
              className="lp-input"
              type={showPw ? 'text' : 'password'}
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={6}
            />
            <button type="button" className="lp-pw-btn" onClick={() => setShowPw(s => !s)}>
              {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>

          {error && <div className="lp-error">{error}</div>}

          <button type="submit" className="lp-submit" disabled={loading}>
            {loading ? 'Please wait...' : (mode === 'login' ? 'Sign In' : 'Create Account')}
          </button>

          {mode === 'signup' && (
            <p className="lp-note">You'll get <strong>100 free credits</strong></p>
          )}
        </form>
      </div>
    </div>
  )
}
