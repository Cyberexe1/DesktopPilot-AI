import React, { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)
const API = 'http://localhost:8000'

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  // Check localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('cipher_user')
    if (saved) {
      try { setUser(JSON.parse(saved)) } catch {}
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()

      if (res.ok && data.data?.success) {
        const userData = data.data.user
        setUser(userData)
        localStorage.setItem('cipher_user', JSON.stringify(userData))
        return { success: true }
      } else {
        const error = data.detail?.error || data.data?.error || 'Login failed'
        return { success: false, error }
      }
    } catch (e) {
      return { success: false, error: 'Cannot connect to server. Is the agent running?' }
    }
  }

  const signup = async (name, email, password) => {
    try {
      const res = await fetch(`${API}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      })
      const data = await res.json()

      if (res.ok && data.data?.success) {
        const userData = data.data.user
        setUser(userData)
        localStorage.setItem('cipher_user', JSON.stringify(userData))
        return { success: true }
      } else {
        const error = data.detail?.error || data.data?.error || 'Signup failed'
        return { success: false, error }
      }
    } catch (e) {
      return { success: false, error: 'Cannot connect to server. Is the agent running?' }
    }
  }

  const logout = () => {
    setUser(null)
    localStorage.removeItem('cipher_user')
  }

  const isAuthenticated = !!user

  return (
    <AuthContext.Provider value={{ user, login, signup, logout, isAuthenticated, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
