import React, { useState, useEffect, useCallback } from 'react'
import { FolderOpen, Search, FileText, File, RefreshCw, ExternalLink } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './FilesPanel.css'

const EXT_ICON = {
  pdf: '📄', docx: '📝', doc: '📝', xlsx: '📊', xls: '📊',
  pptx: '📊', ppt: '📊', py: '🐍', js: '🟨', ts: '🔷',
  jsx: '⚛', tsx: '⚛', json: '{}', md: '📋', txt: '📃',
  html: '🌐', css: '🎨', zip: '📦', png: '🖼', jpg: '🖼',
}

function getIcon(filename) {
  const ext = filename.split('.').pop()?.toLowerCase()
  return EXT_ICON[ext] || '📄'
}

export default function FilesPanel() {
  const { getFiles, reindexFiles, addLog } = useAgent()
  const [files,   setFiles]   = useState([])
  const [query,   setQuery]   = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async (q = '') => {
    setLoading(true)
    try {
      const result = await getFiles(q)
      setFiles(result)
    } catch (e) {
      addLog('File search error: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [getFiles, addLog])

  const handleReindex = async () => {
    setLoading(true)
    try {
      const count = await reindexFiles()
      addLog(`Re-indexed ${count} files`, 'success')
      await load(query)
    } catch (e) {
      addLog('Reindex error: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load('') }, [load])

  useEffect(() => {
    const t = setTimeout(() => load(query), 300)
    return () => clearTimeout(t)
  }, [query, load])

  const openFile = async (path) => {
    try {
      await fetch('http://localhost:8000/files/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      addLog(`Opened: ${path.split('\\').pop()}`, 'success')
    } catch (e) {
      addLog('Failed to open file: ' + e.message, 'error')
    }
  }

  return (
    <div className="panel files-panel">
      <div className="panel-header">
        <span className="panel-title">
          <FolderOpen size={15} className="panel-title-icon" /> File Browser
        </span>
        <button className="btn-icon" onClick={handleReindex} title="Re-index files">
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div className="files-search">
        <Search size={13} className="search-icon text-muted" />
        <input
          className="input search-input"
          placeholder="Search files..."
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </div>

      <div className="panel-body files-body">
        {loading && files.length === 0 && (
          <div className="empty-state">
            <RefreshCw size={28} className="empty-state-icon spin" />
            <p className="text-sm">Scanning files...</p>
          </div>
        )}

        {!loading && files.length === 0 && (
          <div className="empty-state">
            <FolderOpen size={28} className="empty-state-icon" />
            <p className="text-sm">No files found</p>
            <p className="text-xs text-muted">Try a different search term</p>
          </div>
        )}

        {files.length > 0 && (
          <ul className="files-list">
            {files.map((f, i) => (
              <li key={i} className="file-item" onDoubleClick={() => openFile(f.path)}>
                <span className="file-icon">{getIcon(f.name)}</span>
                <div className="file-info">
                  <span className="file-name truncate">{f.name}</span>
                  <span className="file-path truncate text-xs text-muted">{f.path}</span>
                </div>
                <button
                  className="btn-icon file-open-btn"
                  onClick={() => openFile(f.path)}
                  title="Open file"
                >
                  <ExternalLink size={12} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="files-footer">
        <span className="text-xs text-muted">{files.length} file{files.length !== 1 ? 's' : ''}</span>
        <span className="text-xs text-muted">Double-click to open</span>
      </div>
    </div>
  )
}
