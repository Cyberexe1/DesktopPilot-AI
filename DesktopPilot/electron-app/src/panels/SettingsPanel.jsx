import React, { useState, useEffect } from 'react'
import { Settings, Save, RefreshCw, ExternalLink, AlertTriangle, CheckCircle } from 'lucide-react'
import { useAgent } from '../context/AgentContext'
import './SettingsPanel.css'

const DEFAULT_SETTINGS = {
  aws_region:    'us-east-1',
  s3_bucket:     '',
  bedrock_model: 'anthropic.claude-3-sonnet-20240229-v1:0',
  dynamo_table:  'DesktopPilotMemory',
  scan_dirs:     'Desktop,Documents,Downloads',
  require_approval_terminal: true,
  require_approval_email:    true,
  require_approval_settings: true,
}

export default function SettingsPanel() {
  const { backendReady, addLog, wsConnected, reindexFiles } = useAgent()
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [saved,    setSaved]    = useState(false)
  const [testing,  setTesting]  = useState(false)
  const [testResult, setTestResult] = useState(null)

  const set = (key, val) => setSettings(s => ({ ...s, [key]: val }))

  const handleSave = () => {
    // Phase 3: persist to backend config
    localStorage.setItem('dp_settings', JSON.stringify(settings))
    setSaved(true)
    addLog('Settings saved', 'success')
    setTimeout(() => setSaved(false), 2000)
  }

  const testBackend = async () => {
    setTesting(true); setTestResult(null)
    try {
      const res = await fetch('http://localhost:8000/health', { signal: AbortSignal.timeout(3000) })
      const data = await res.json()
      setTestResult({ ok: true, msg: `Backend OK — ${data.agent}` })
    } catch (e) {
      setTestResult({ ok: false, msg: 'Backend not reachable: ' + e.message })
    } finally { setTesting(false) }
  }

  useEffect(() => {
    const saved = localStorage.getItem('dp_settings')
    if (saved) try { setSettings(JSON.parse(saved)) } catch {}
  }, [])

  return (
    <div className="panel settings-panel">
      <div className="panel-header">
        <span className="panel-title">
          <Settings size={15} className="panel-title-icon" /> Settings
        </span>
        <button className="btn btn-primary" onClick={handleSave}>
          {saved ? <><CheckCircle size={13} /> Saved!</> : <><Save size={13} /> Save</>}
        </button>
      </div>

      <div className="panel-body settings-body">

        {/* Backend status */}
        <div className="card settings-section">
          <p className="section-label">Backend Status</p>
          <div className="backend-status">
            <div className={`status-row ${backendReady ? 'status-ok' : 'status-warn'}`}>
              <span className="status-dot-sm" />
              <span className="text-sm">FastAPI — {backendReady ? 'Running on :8000' : 'Starting...'}</span>
            </div>
            <div className={`status-row ${wsConnected ? 'status-ok' : 'status-warn'}`}>
              <span className="status-dot-sm" />
              <span className="text-sm">WebSocket — {wsConnected ? 'Connected (/ws)' : 'Disconnected'}</span>
            </div>
            <div className="status-actions">
              <button className="btn btn-secondary" onClick={testBackend} disabled={testing}>
                {testing ? <RefreshCw size={12} className="spin" /> : <RefreshCw size={12} />}
                Test Connection
              </button>
              <button className="btn btn-secondary" onClick={() => window.dp?.restartBackend()}>
                Restart Backend
              </button>
              <button className="btn btn-secondary" onClick={async () => {
                const n = await reindexFiles()
                addLog(`Re-indexed ${n} files`, 'success')
              }}>
                Re-index Files
              </button>
            </div>
            {testResult && (
              <div className={`test-result ${testResult.ok ? 'result-ok' : 'result-fail'}`}>
                {testResult.ok ? <CheckCircle size={13} /> : <AlertTriangle size={13} />}
                <span className="text-xs">{testResult.msg}</span>
              </div>
            )}
          </div>
        </div>

        {/* AWS Config */}
        <div className="card settings-section">
          <p className="section-label">AWS Configuration</p>
          <div className="settings-note">
            <AlertTriangle size={12} className="text-warning" />
            <span className="text-xs text-muted">
              AWS credentials are read from the backend <code>.env</code> file, not stored here.
            </span>
          </div>
          <div className="settings-fields">
            <SettingField label="AWS Region" value={settings.aws_region}
              onChange={v => set('aws_region', v)} placeholder="us-east-1" />
            <SettingField label="S3 Bucket" value={settings.s3_bucket}
              onChange={v => set('s3_bucket', v)} placeholder="desktoppilot-audio" />
            <SettingField label="Bedrock Model ID" value={settings.bedrock_model}
              onChange={v => set('bedrock_model', v)} placeholder="anthropic.claude-3-sonnet..." />
            <SettingField label="DynamoDB Table" value={settings.dynamo_table}
              onChange={v => set('dynamo_table', v)} placeholder="DesktopPilotMemory" />
          </div>
        </div>

        {/* File indexer */}
        <div className="card settings-section">
          <p className="section-label">File Indexer</p>
          <SettingField
            label="Scan Directories (comma-separated)"
            value={settings.scan_dirs}
            onChange={v => set('scan_dirs', v)}
            placeholder="Desktop,Documents,Downloads,D:/Projects"
          />
        </div>

        {/* Approval rules */}
        <div className="card settings-section">
          <p className="section-label">Approval Rules</p>
          <p className="text-xs text-muted" style={{ marginBottom: '0.75rem' }}>
            Choose which actions require your approval before execution.
          </p>
          <div className="toggle-list">
            <ToggleField label="Terminal commands (run_terminal)"
              value={settings.require_approval_terminal}
              onChange={v => set('require_approval_terminal', v)} />
            <ToggleField label="Email composition (compose_email)"
              value={settings.require_approval_email}
              onChange={v => set('require_approval_email', v)} />
            <ToggleField label="System settings (open_setting)"
              value={settings.require_approval_settings}
              onChange={v => set('require_approval_settings', v)} />
          </div>
        </div>

        {/* Links */}
        <div className="card settings-section">
          <p className="section-label">Links</p>
          <div className="links-list">
            {[
              { label: 'Web Dashboard', url: 'https://desktoppilot.vercel.app/dashboard' },
              { label: 'Buy Credits', url: 'https://desktoppilot.vercel.app/dashboard#credits' },
              { label: 'AWS Console', url: 'https://console.aws.amazon.com' },
              { label: 'Bedrock Models', url: 'https://console.aws.amazon.com/bedrock' },
            ].map((l, i) => (
              <button key={i} className="link-btn text-sm"
                onClick={() => window.dp?.openExternal(l.url)}>
                <ExternalLink size={12} /> {l.label}
              </button>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

function SettingField({ label, value, onChange, placeholder }) {
  return (
    <div className="setting-field">
      <label className="text-xs text-muted">{label}</label>
      <input className="input font-mono text-xs" value={value}
        onChange={e => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  )
}

function ToggleField({ label, value, onChange }) {
  return (
    <label className="toggle-row">
      <span className="text-sm">{label}</span>
      <div className={`toggle ${value ? 'toggle-on' : ''}`} onClick={() => onChange(!value)}>
        <div className="toggle-thumb" />
      </div>
    </label>
  )
}
