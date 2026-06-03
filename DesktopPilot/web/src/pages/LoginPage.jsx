import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LogIn, UserPlus, Eye, EyeOff } from 'lucide-react'
import './LoginPage.css'

export default function LoginPage() {
  const { login, signup } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode]         = useState('login') // 'login' or 'signup'
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

    let result
    if (mode === 'signup') {
      result = await signup(name, email, password)
    } else {
      result = await login(email, password)
    }

    setLoading(false)
    if (result.success) {
      navigate('/dashboard')
    } else {
      setError(result.error)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1 className="login-brand">Cipher AI</h1>
          <p className="login-sub">
            {mode === 'login' ? 'Sign in to your dashboard' : 'Create a new account'}
          </p>
        </div>

        {/* Toggle tabs */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === 'login' ? 'auth-tab-active' : ''}`}
            onClick={() => { setMode('login'); setError('') }}
          >
            <LogIn size={14} /> Sign In
          </button>
          <button
            className={`auth-tab ${mode === 'signup' ? 'auth-tab-active' : ''}`}
            onClick={() => { setMode('signup'); setError('') }}
          >
            <UserPlus size={14} /> Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {mode === 'signup' && (
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="Vikas Tiwari"
                value={name}
                onChange={e => setName(e.target.value)}
                required
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              type="email"
              className="form-input"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="password-wrapper">
              <input
                type={showPw ? 'text' : 'password'}
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
              />
              <button type="button" className="pw-toggle" onClick={() => setShowPw(s => !s)}>
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {mode === 'signup' && (
              <span className="form-hint">Minimum 6 characters</span>
            )}
          </div>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? 'Please wait...' : (
              mode === 'login'
                ? <><LogIn size={16} /> Sign In</>
                : <><UserPlus size={16} /> Create Account</>
            )}
          </button>

          {mode === 'signup' && (
            <p className="signup-note">You'll get <strong>100 free credits</strong> to start.</p>
          )}
        </form>
      </div>
    </div>
  )
}
