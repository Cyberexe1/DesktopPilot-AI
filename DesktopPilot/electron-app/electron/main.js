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
const { spawn } = require('child_process')
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
})

app.on('before-quit', () => {
  isQuitting = true
  stopFastAPI()
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
        'Cipher AI',
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
      label: 'Cipher AI',
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
      label: '❌  Quit Cipher AI',
      click: () => { isQuitting = true; app.quit() }
    },
  ])
  tray.setContextMenu(menu)

  // Update tooltip
  tray.setToolTip(fastapiRunning ? 'Cipher AI — Agent Ready' : 'Cipher AI — Starting...')
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
    showNotification('Cipher AI', 'Backend not ready yet. Open the app first.')
  }
}

// ── FastAPI Backend ───────────────────────────────────────────────────────────
function startFastAPI() {
  const backendDir = IS_DEV
    ? path.join(__dirname, '../../backend')
    : path.join(process.resourcesPath, 'backend')

  const python = process.platform === 'win32' ? 'python' : 'python3'

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
  if (fastapiProc) {
    fastapiProc.kill('SIGTERM')
    fastapiProc = null
  }
}

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
