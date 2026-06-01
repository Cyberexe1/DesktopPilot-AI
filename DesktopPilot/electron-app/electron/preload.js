/**
 * Preload — exposes a safe contextBridge API to the renderer.
 */
const { contextBridge, ipcRenderer } = require('electron')

const ALLOWED_CHANNELS = [
  'fastapi:status',
  'fastapi:log',
  'ws:status',
  'ws:client-count',
  'execution:update',
]

contextBridge.exposeInMainWorld('dp', {
  // ── Window controls ────────────────────────────────────────────────────────
  minimize:     () => ipcRenderer.invoke('window:minimize'),
  maximize:     () => ipcRenderer.invoke('window:maximize'),
  close:        () => ipcRenderer.invoke('window:close'),
  isMaximized:  () => ipcRenderer.invoke('window:isMaximized'),

  // ── Agent ──────────────────────────────────────────────────────────────────
  getStatus:       () => ipcRenderer.invoke('agent:status'),
  restartBackend:  () => ipcRenderer.invoke('agent:restartBackend'),

  // ── Shell ──────────────────────────────────────────────────────────────────
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  openFolder:   ()    => ipcRenderer.invoke('dialog:openFolder'),

  // ── Events from main → renderer ────────────────────────────────────────────
  on: (channel, cb) => {
    if (ALLOWED_CHANNELS.includes(channel)) {
      ipcRenderer.on(channel, (_, data) => cb(data))
    }
  },
  off: (channel) => {
    if (ALLOWED_CHANNELS.includes(channel)) {
      ipcRenderer.removeAllListeners(channel)
    }
  },
})
