import React, { useState, useEffect, useCallback } from 'react'
import { Clipboard, Search, RefreshCw, Copy, Code, Mail, Link, Phone, MapPin, Hash, FileText, Trash2 } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './ClipboardPanel.css'

const API = 'http://localhost:8888'

const TAG_ICONS = {
  code:    <Code size={10} />,
  email:   <Mail size={10} />,
  url:     <Link size={10} />,
  phone:   <Phone size={10} />,
  address: <MapPin size={10} />,
  number:  <Hash size={10} />,
  text:    <FileText size={10} />,
  other:   <Clipboard size={10} />,
}

const TAG_FILTERS = ['all', 'code', 'email', 'url', 'phone', 'text', 'other']

export default function ClipboardPanel() {
  const { addLog } = useAgent()
  const [entries,  setEntries]  = useState([])
  const [filter,   setFilter]   = useState('all')
  const [query,    setQuery]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [aiQuery,  setAiQuery]  = useState('')
  const [aiAnswer, setAiAnswer] = useState('')
  const [aiLoading,setAiLoading]= useState(false)
  const [copiedId, setCopiedId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res  = await fetch(`${API}/clipboard/history?limit=50`)
      const data = await res.json()
      setEntries(data.data?.entries ?? [])
    } catch (e) {
      addLog('Clipboard load error: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [addLog])

  useEffect(() => { load() }, [load])

  // auto-refresh every 3s to catch new copies
  useEffect(() => {
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [load])

  const handlePaste = async (entry) => {
    try {
      await fetch(`${API}/clipboard/paste`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry_id: entry.id }),
      })
      setCopiedId(entry.id)
      setTimeout(() => setCopiedId(null), 1500)
      addLog(`Pasted: ${entry.preview}`, 'success')
    } catch (e) {
      addLog('Paste failed: ' + e.message, 'error')
    }
  }

  const handleClear = async () => {
    try {
      await fetch(`${API}/clipboard/history`, { method: 'DELETE' })
      setEntries([])
      addLog('Clipboard history cleared', 'info')
    } catch (e) {
      addLog('Clear failed: ' + e.message, 'error')
    }
  }

  const handleAiQuery = async (e) => {
    e.preventDefault()
    if (!aiQuery.trim()) return
    setAiLoading(true)
    setAiAnswer('')
    try {
      const res  = await fetch(`${API}/clipboard/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: aiQuery }),
      })
      const data = await res.json()
      setAiAnswer(data.data?.answer ?? '')
    } catch (e) {
      setAiAnswer('Query failed: ' + e.message)
    } finally {
      setAiLoading(false)
    }
  }

  // Filter + search
  const visible = entries.filter(e => {
    const matchTag   = filter === 'all' || e.tag === filter
    const matchQuery = !query || e.text.toLowerCase().includes(query.toLowerCase())
    return matchTag && matchQuery
  })

  return (
    <div className="panel clipboard-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Clipboard size={15} className="panel-title-icon" /> AI Clipboard
        </span>
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button className="btn-icon" onClick={load} title="Refresh">
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
          </button>
          <button className="btn-icon" onClick={handleClear} title="Clear history">
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      <div className="cb-controls">
        {/* Tag filter pills */}
        <div className="cb-filters">
          {TAG_FILTERS.map(tag => (
            <button
              key={tag}
              className={`cb-filter-btn ${filter === tag ? 'cb-filter-active' : ''}`}
              onClick={() => setFilter(tag)}
            >
              {tag === 'all' ? 'All' : tag}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="cb-search-wrap">
          <Search size={11} className="cb-search-icon text-muted" />
          <input
            className="input cb-search"
            placeholder="Search clipboard history…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>

        {/* AI query */}
        <form className="cb-ai-form" onSubmit={handleAiQuery}>
          <input
            className="input"
            placeholder='Ask AI: "paste my last code snippet"'
            value={aiQuery}
            onChange={e => setAiQuery(e.target.value)}
          />
          <button
            type="submit"
            className="btn btn-primary cb-ai-btn"
            disabled={!aiQuery.trim() || aiLoading}
          >
            {aiLoading ? <RefreshCw size={11} className="spin" /> : 'Ask'}
          </button>
        </form>
        {aiAnswer && (
          <div className="cb-ai-answer card">
            <p className="text-xs selectable" style={{ lineHeight: 1.6 }}>{aiAnswer}</p>
          </div>
        )}
      </div>

      <div className="panel-body cb-body">
        {visible.length === 0 && !loading && (
          <div className="empty-state">
            <Clipboard size={28} className="empty-state-icon" />
            <p className="text-sm">No clipboard entries</p>
            <p className="text-xs text-muted">Copy anything — it will appear here automatically</p>
          </div>
        )}

        <ul className="cb-list">
          {visible.map((entry, i) => (
            <li
              key={entry.id}
              className="cb-item"
              style={{ animationDelay: `${i * 0.03}s` }}
            >
              <div className="cb-item-tag">
                <span className={`cb-tag cb-tag--${entry.tag}`}>
                  {TAG_ICONS[entry.tag] || TAG_ICONS.other}
                  {entry.tag}
                </span>
              </div>
              <div className="cb-item-content">
                <p className="cb-preview selectable">{entry.preview}</p>
                <p className="cb-meta text-xs text-muted">
                  {entry.timestamp} · {entry.length} chars
                </p>
              </div>
              <button
                className={`btn-icon cb-copy-btn ${copiedId === entry.id ? 'cb-copied' : ''}`}
                onClick={() => handlePaste(entry)}
                title="Copy to clipboard"
              >
                {copiedId === entry.id ? '✓' : <Copy size={12} />}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="cb-footer">
        <span className="text-xs text-muted">{entries.length} entries tracked</span>
        <span className="text-xs text-muted" style={{ color: '#22c55e' }}>● Live</span>
      </div>
    </div>
  )
}
