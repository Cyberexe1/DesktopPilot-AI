import React, { useState, useEffect } from 'react'
import { GitBranch, Plus, Play, FolderOpen, Trash2, Code } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './ProjectsPanel.css'

const FRAMEWORKS = ['Django', 'FastAPI', 'React', 'Next.js', 'Node.js', 'Vue', 'Angular', 'Flask', 'Other']

export default function ProjectsPanel() {
  const { getProjects, addProject, addLog } = useAgent()
  const [projects, setProjects] = useState([])
  const [showAdd,  setShowAdd]  = useState(false)
  const [form,     setForm]     = useState({ name: '', path: '', framework: 'Django', start_command: '' })
  const [loading,  setLoading]  = useState(false)

  const load = async () => {
    try { setProjects(await getProjects()) } catch (e) { addLog(e.message, 'error') }
  }

  useEffect(() => { load() }, [])

  const handleAdd = async () => {
    if (!form.name || !form.path) return
    setLoading(true)
    try {
      await addProject(form)
      addLog(`Project registered: ${form.name}`, 'success')
      setForm({ name: '', path: '', framework: 'Django', start_command: '' })
      setShowAdd(false)
      load()
    } catch (e) {
      addLog('Failed to add project: ' + e.message, 'error')
    } finally { setLoading(false) }
  }

  const browseFolder = async () => {
    const folder = await window.dp?.openFolder()
    if (folder) {
      const name = folder.split('\\').pop() || folder.split('/').pop()
      setForm(f => ({ ...f, path: folder, name: f.name || name }))
    }
  }

  const openInVSCode = async (name) => {
    try {
      await fetch('http://localhost:8000/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: { tasks: [{ tool: 'open_project', project: name }] } }),
      })
      addLog(`Opened in VS Code: ${name}`, 'success')
    } catch (e) { addLog(e.message, 'error') }
  }

  const launchProject = async (project) => {
    if (!project.start_command) { addLog('No start command configured', 'warning'); return }
    try {
      await fetch('http://localhost:8000/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan: { tasks: [{ tool: 'run_terminal', command: project.start_command, project: project.name }] }
        }),
      })
      addLog(`Launched: ${project.name}`, 'success')
    } catch (e) { addLog(e.message, 'error') }
  }

  return (
    <div className="panel projects-panel">
      <div className="panel-header">
        <span className="panel-title">
          <GitBranch size={15} className="panel-title-icon" /> Projects
        </span>
        <button className="btn btn-primary" onClick={() => setShowAdd(s => !s)}>
          <Plus size={13} /> Add Project
        </button>
      </div>

      <div className="panel-body">
        {/* Add form */}
        {showAdd && (
          <div className="card add-form">
            <p className="section-label">Register New Project</p>
            <div className="form-grid">
              <div className="form-field">
                <label className="form-label text-xs text-muted">Project Name</label>
                <input className="input" placeholder="EduPulse"
                  value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="form-field">
                <label className="form-label text-xs text-muted">Framework</label>
                <select className="input" value={form.framework}
                  onChange={e => setForm(f => ({ ...f, framework: e.target.value }))}>
                  {FRAMEWORKS.map(fw => <option key={fw}>{fw}</option>)}
                </select>
              </div>
              <div className="form-field form-field-full">
                <label className="form-label text-xs text-muted">Project Path</label>
                <div className="path-row">
                  <input className="input" placeholder="D:/Projects/EduPulse"
                    value={form.path} onChange={e => setForm(f => ({ ...f, path: e.target.value }))} />
                  <button className="btn btn-secondary" onClick={browseFolder}>
                    <FolderOpen size={13} /> Browse
                  </button>
                </div>
              </div>
              <div className="form-field form-field-full">
                <label className="form-label text-xs text-muted">Start Command</label>
                <input className="input font-mono" placeholder="python manage.py runserver"
                  value={form.start_command} onChange={e => setForm(f => ({ ...f, start_command: e.target.value }))} />
              </div>
            </div>
            <div className="form-actions">
              <button className="btn btn-primary" onClick={handleAdd} disabled={loading || !form.name || !form.path}>
                {loading ? 'Saving...' : 'Save Project'}
              </button>
              <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>Cancel</button>
            </div>
          </div>
        )}

        {/* Project list */}
        {projects.length === 0 && !showAdd && (
          <div className="empty-state">
            <GitBranch size={28} className="empty-state-icon" />
            <p className="text-sm">No projects registered</p>
            <p className="text-xs text-muted">Click "Add Project" to register your first project</p>
          </div>
        )}

        <div className="projects-list">
          {projects.map((p, i) => (
            <div key={i} className="card project-card">
              <div className="project-header">
                <div className="project-info">
                  <span className="project-name">{p.name}</span>
                  <span className="badge badge-blue text-xs">{p.framework}</span>
                </div>
                <div className="project-actions">
                  <button className="btn-icon" title="Open in VS Code" onClick={() => openInVSCode(p.name)}>
                    <Code size={14} />
                  </button>
                  <button className="btn-icon" title="Launch" onClick={() => launchProject(p)}>
                    <Play size={14} />
                  </button>
                </div>
              </div>
              <p className="project-path text-xs text-muted font-mono truncate">{p.path}</p>
              {p.start_command && (
                <p className="project-cmd text-xs text-muted font-mono">$ {p.start_command}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
