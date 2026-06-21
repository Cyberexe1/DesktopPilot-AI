/**
 * DesktopPilot AI — Electron Main Process
 *
 * Full desktop application (like Kiro / VS Code style).
 * Spawns the FastAPI backend, manages system tray, handles IPC.
 */

const {
  app, BrowserWindow, Tray, Menu, nativeImage,
  ipcMain, shell, Notification, dialog
} = require('electron')
const path    = require('path')
const { spawn, spawnSync } = require('child_process')
const http    = require('http')
const fs      = require('fs')

// ── Constants ─────────────────────────────────────────────────────────────────
const IS_DEV       = process.env.NODE_ENV === 'development' || !app.isPackaged
const FASTAPI_PORT = 8888
const RENDERER_URL = IS_DEV
  ? 'http://localhost:5174'
  : `file://${path.join(__dirname, '../dist/index.html')}`

// ── State ─────────────────────────────────────────────────────────────────────
let mainWindow    = null
let tray          = null
let fastapiProc   = null
let wakeProc      = null   // pvporcupine wake word listener
let isQuitting    = false
let backendReady  = false

// ── Start on Windows login ────────────────────────────────────────────────────
if (!IS_DEV) {
  app.setLoginItemSettings({
    openAtLogin: true,
    name: 'DesktopPilot AI',
  })
}

// ── Single instance lock ──────────────────────────────────────────────────────
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  createWindow()
  createTray()
  startFastAPI()
  // Start wake word listener after a short delay (backend needs to be up first)
  setTimeout(startWakeListener, 6000)
})

app.on('before-quit', () => {
  isQuitting = true
  stopFastAPI()
  stopWakeListener()
})

app.on('window-all-closed', () => {
  // On Windows keep running in tray
  if (process.platform === 'darwin') app.quit()
})

// ── Main Window ───────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width:           1280,
    height:          800,
    minWidth:        900,
    minHeight:       600,
    frame:           false,        // Custom title bar
    backgroundColor: '#0d0f14',
    icon:            getIconPath(),
    show:            false,        // Show after ready-to-show
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload:          path.join(__dirname, 'preload.js'),
    },
  })

  mainWindow.loadURL(RENDERER_URL)

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  if (IS_DEV) {
    // DevTools disabled — uncomment below to re-enable for debugging
    // mainWindow.webContents.openDevTools({ mode: 'right' })
  }

  // Minimize to tray on close — don't quit
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow.hide()
      showNotification(
        'DesktopPilot AI',
        'Minimized to tray. Say "Hey Cipher" anytime, or click the tray icon.'
      )
    }
  })
}

// ── System Tray ───────────────────────────────────────────────────────────────
function createTray() {
  const iconPath = getIconPath()
  const icon     = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
    : nativeImage.createEmpty()

  tray = new Tray(icon)
  tray.setToolTip('DesktopPilot AI')
  updateTrayMenu()

  tray.on('double-click', () => {
    showWindow()
  })

  // Single click also shows window on Windows
  tray.on('click', () => {
    showWindow()
  })
}

function updateTrayMenu(fastapiRunning = false) {
  if (!tray) return
  backendReady = fastapiRunning

  const menu = Menu.buildFromTemplate([
    {
      label: 'DesktopPilot AI',
      enabled: false,
      icon: nativeImage.createEmpty(),
    },
    {
      label: `  ${fastapiRunning ? '🟢 Agent Ready' : '🟡 Starting...'}`,
      enabled: false,
    },
    { type: 'separator' },
    // ── Quick Actions ──
    {
      label: '🎤  Open Voice Panel',
      click: () => {
        showWindow()
        mainWindow?.webContents.send('navigate:panel', 'voice')
      }
    },
    {
      label: '📸  Take Screenshot',
      enabled: fastapiRunning,
      click: () => quickCommand('take a screenshot')
    },
    {
      label: '🔋  Battery Status',
      enabled: fastapiRunning,
      click: () => quickCommand('how much battery do I have')
    },
    {
      label: '🔇  Mute / Unmute',
      enabled: fastapiRunning,
      click: () => quickCommand('mute')
    },
    {
      label: '🌙  Minimize All Windows',
      enabled: fastapiRunning,
      click: () => quickCommand('minimize everything')
    },
    { type: 'separator' },
    // ── Window ──
    {
      label: '🪟  Show Window',
      click: () => showWindow()
    },
    {
      label: '📊  Open Dashboard',
      click: () => shell.openExternal('https://desktoppilot.vercel.app/dashboard')
    },
    { type: 'separator' },
    {
      label: '⚙  Restart Backend',
      enabled: true,
      click: () => {
        stopFastAPI()
        setTimeout(startFastAPI, 800)
        showNotification('DesktopPilot AI', 'Restarting backend...')
      }
    },
    { type: 'separator' },
    {
      label: '❌  Quit DesktopPilot AI',
      click: () => { isQuitting = true; app.quit() }
    },
  ])
  tray.setContextMenu(menu)

  // Update tooltip
  tray.setToolTip(fastapiRunning ? 'DesktopPilot AI — Agent Ready' : 'DesktopPilot AI — Starting...')
}

function showWindow() {
  if (!mainWindow) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

function showNotification(title, body) {
  if (Notification.isSupported()) {
    new Notification({ title, body }).show()
  }
}

async function quickCommand(command) {
  // Execute a quick command directly via the backend API (no UI needed)
  try {
    const planRes = await fetch(`http://127.0.0.1:${FASTAPI_PORT}/plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: command }),
    })
    const planData = await planRes.json()
    if (planData.data?.plan) {
      await fetch(`http://127.0.0.1:${FASTAPI_PORT}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: planData.data.plan }),
      })
    }
  } catch (e) {
    console.error(`Quick command failed: ${e.message}`)
    showNotification('DesktopPilot AI', 'Backend not ready yet. Open the app first.')
  }
}

// ── FastAPI Backend ───────────────────────────────────────────────────────────

// Resolve a working Python interpreter once. GUI apps don't always get the same
// PATH as a terminal, and the launcher may be `py` (python.org) instead of
// `python`, so we probe a few candidates with `--version`.
let pythonCmd = null
function resolvePython() {
  if (pythonCmd) return pythonCmd
  const candidates = process.platform === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python']
  for (const cmd of candidates) {
    try {
      const r = spawnSync(cmd, ['--version'], { stdio: 'ignore' })
      if (!r.error && r.status === 0) {
        pythonCmd = cmd
        console.log(`[Python] Using interpreter: ${cmd}`)
        return cmd
      }
    } catch (_) { /* try next */ }
  }
  return null
}

function startFastAPI() {
  const backendDir = IS_DEV
    ? path.join(__dirname, '../../backend')
    : path.join(process.resourcesPath, 'backend')

  const python = resolvePython()
  if (!python) {
    console.error('[FastAPI] Python not found on PATH')
    mainWindow?.webContents.send('fastapi:status', { running: false, error: 'python-not-found' })
    updateTrayMenu(false)
    showNotification(
      'DesktopPilot AI',
      'Python was not found. Install Python 3.11+ and make sure it is on your PATH, then reopen the app.'
    )
    return
  }

  console.log(`[FastAPI] Starting from: ${backendDir}`)

  fastapiProc = spawn(
    python,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(FASTAPI_PORT), '--log-level', 'info'],
    {
      cwd:   backendDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env:   { ...process.env },
    }
  )

  // Without this, a failed spawn (e.g. ENOENT) becomes an uncaught exception
  // and crashes the whole app with a JavaScript error dialog.
  fastapiProc.on('error', (err) => {
    console.error(`[FastAPI] Failed to start: ${err.message}`)
    mainWindow?.webContents.send('fastapi:status', { running: false, error: err.message })
    updateTrayMenu(false)
    showNotification('DesktopPilot AI', `Backend failed to start: ${err.message}`)
    fastapiProc = null
  })

  fastapiProc.stdout.on('data', (d) => {
    const msg = d.toString().trim()
    if (msg) {
      console.log(`[FastAPI] ${msg}`)
      mainWindow?.webContents.send('fastapi:log', { level: 'info', msg })
    }
  })

  fastapiProc.stderr.on('data', (d) => {
    const msg = d.toString().trim()
    if (msg) {
      console.error(`[FastAPI ERR] ${msg}`)
      mainWindow?.webContents.send('fastapi:log', { level: 'error', msg })
    }
  })

  fastapiProc.on('exit', (code) => {
    console.log(`[FastAPI] Exited with code ${code}`)
    mainWindow?.webContents.send('fastapi:status', { running: false, code })
    updateTrayMenu(false)
  })

  pollFastAPI()
}

function pollFastAPI(attempt = 0) {
  if (attempt > 40) {
    mainWindow?.webContents.send('fastapi:status', { running: false, error: 'Startup timeout' })
    return
  }
  setTimeout(() => {
    http.get(`http://127.0.0.1:${FASTAPI_PORT}/health`, (res) => {
      if (res.statusCode === 200) {
        console.log('[FastAPI] Ready ✓')
        mainWindow?.webContents.send('fastapi:status', { running: true })
        updateTrayMenu(true)
      } else {
        pollFastAPI(attempt + 1)
      }
    }).on('error', () => pollFastAPI(attempt + 1))
  }, 1000)
}

function stopFastAPI() {
  killProcessTree(fastapiProc)
  fastapiProc = null
}

// ── Wake Word Listener (pvporcupine — always-on background process) ────────────
function startWakeListener() {
  const backendDir = IS_DEV
    ? path.join(__dirname, '../../backend')
    : path.join(process.resourcesPath, 'backend')

  const python = resolvePython()
  if (!python) {
    console.log('[Wake] Python not found — skipping wake word listener')
    return
  }
  const script = path.join(backendDir, 'voice', 'wake_listener.py')

  if (!fs.existsSync(script)) {
    console.log('[Wake] wake_listener.py not found — skipping wake word')
    return
  }

  console.log('[Wake] Starting pvporcupine wake word listener...')

  wakeProc = spawn(python, [script], {
    cwd:   backendDir,
    stdio: ['ignore', 'pipe', 'pipe'],
    env:   { ...process.env },
  })

  // Handle spawn failure so it never crashes the main process.
  wakeProc.on('error', (err) => {
    console.error(`[Wake] Failed to start: ${err.message}`)
    wakeProc = null
  })

  // Read stdout line by line — this is how wake_listener.py sends IPC signals
  let buffer = ''
  wakeProc.stdout.on('data', (data) => {
    buffer += data.toString()
    const lines = buffer.split('\n')
    buffer = lines.pop()  // Keep incomplete line in buffer

    for (const line of lines) {
      const msg = line.trim()
      if (!msg) continue

      if (msg === 'WAKE_READY') {
        console.log('[Wake] Listener ready ✓')
        mainWindow?.webContents.send('wake:ready')

      } else if (msg === 'WAKE_DETECTED') {
        console.log('[Wake] Wake word detected!')
        // Tell the renderer to activate voice listening
        mainWindow?.webContents.send('wake:detected')
        // Show window if it was hidden
        showWindow()

      } else if (msg.startsWith('WAKE_ERROR:')) {
        const errMsg = msg.replace('WAKE_ERROR:', '')
        console.error(`[Wake] Error: ${errMsg}`)
        mainWindow?.webContents.send('wake:error', errMsg)
      }
    }
  })

  wakeProc.stderr.on('data', (d) => {
    // Suppress — wake listener is noisy with audio library logs
  })

  wakeProc.on('exit', (code) => {
    console.log(`[Wake] Listener exited (code ${code})`)
    wakeProc = null
    // Auto-restart after 5s if not quitting
    if (!isQuitting) {
      setTimeout(startWakeListener, 5000)
    }
  })
}

function stopWakeListener() {
  killProcessTree(wakeProc)
  wakeProc = null
}

// Kill a spawned child process AND its descendants. On Windows a plain
// SIGTERM only kills the direct child (e.g. the python launcher) and can leave
// grandchildren holding file locks, so use taskkill /T to take down the tree.
function killProcessTree(proc) {
  if (!proc || proc.pid == null) return
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(proc.pid), '/t', '/f'])
    } else {
      proc.kill('SIGTERM')
    }
  } catch (e) {
    try { proc.kill('SIGKILL') } catch (_) {}
  }
}

// IPC: renderer can toggle wake listener on/off
ipcMain.handle('wake:start', () => {
  if (!wakeProc) startWakeListener()
  return { ok: true }
})

ipcMain.handle('wake:stop', () => {
  stopWakeListener()
  return { ok: true }
})

// ── IPC Handlers ──────────────────────────────────────────────────────────────

// Window controls
ipcMain.handle('window:minimize',  () => mainWindow?.minimize())
ipcMain.handle('window:maximize',  () => {
  mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize()
})
ipcMain.handle('window:close',     () => mainWindow?.close())
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false)

// Agent status
ipcMain.handle('agent:status', () => ({
  fastapi_port:    FASTAPI_PORT,
  version:         app.getVersion(),
  platform:        process.platform,
  is_dev:          IS_DEV,
}))

// Backend control
ipcMain.handle('agent:restartBackend', () => {
  stopFastAPI()
  setTimeout(startFastAPI, 800)
  return { ok: true }
})

// Open external links
ipcMain.handle('shell:openExternal', (_, url) => shell.openExternal(url))

// Open file dialog (for adding projects)
ipcMain.handle('dialog:openFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Project Folder',
  })
  return result.canceled ? null : result.filePaths[0]
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function getIconPath() {
  const ext  = process.platform === 'win32' ? 'ico' : 'png'
  return path.join(__dirname, `../assets/icon.${ext}`)
}
