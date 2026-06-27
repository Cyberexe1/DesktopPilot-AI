# DesktopPilot AI — Autonomous Voice-Controlled Desktop Agent

> **"Just say what you need. Cipher handles the rest."**

DesktopPilot AI is a full-stack, AI-powered desktop automation platform for Windows. It lets users control their entire computer using plain English voice commands or typed text. You speak a command — "Open my EduPulse project, start the development server, and open it in the browser" — and the system understands, plans, and executes every step automatically, opening VS Code, running the terminal command, waiting for the server to be ready, and launching Chrome, all without touching a single keyboard shortcut.

The project is built as two connected products: a full-window Electron desktop application that acts as the local AI agent, and a React web application deployed on Vercel that serves as the public landing page and user dashboard.

---

## What Problem It Solves

Developers and power users repeat the same multi-step workflows dozens of times a day — spinning up a dev environment, organizing files, composing emails, managing browser tabs, adjusting system settings. These workflows are mental overhead. DesktopPilot AI eliminates that overhead entirely. Instead of remembering keyboard shortcuts, navigating menus, or writing scripts, you describe what you want in natural language and the agent executes it. It is not a chatbot. It is an autonomous agent that actually does things on your computer.

---

## How It Works — End to End

### 1. Voice Input and Transcription

When the user clicks the microphone button (or says the wake word "Hey Cipher"), the Electron renderer captures audio via the browser's MediaRecorder API. The audio blob is sent to the local FastAPI backend at `POST /transcribe`. The backend takes two paths: if faster-whisper (a local Whisper model) is available, it transcribes the audio locally in roughly 200–400ms with no API cost. If local transcription fails or is disabled, it falls back to Amazon Transcribe — uploading the audio file to an S3 bucket, starting a transcription job, and polling until the transcript is ready. The result is a clean text string of what the user said.

### 2. Prompt Enhancement

Before the main AI planner runs, the transcript goes through a prompt enhancer. This is a fast, cheap call to Amazon Bedrock Nova Lite that turns vague or short commands into explicit, actionable instructions. For example, "gmail in chrome" becomes "Open the browser and navigate to https://mail.google.com" and "setup vite project" becomes "Create a new Vite React project called my-app on Desktop." Commands that are already explicit — "open Chrome," "how much battery," "what is machine learning" — are detected and skipped entirely so no unnecessary Bedrock call is made.

### 3. AI Planning (The Brain)

The enhanced command goes to the AI planner at `POST /plan`. The planner sends a carefully structured system prompt to Amazon Bedrock Nova Pro. The system prompt defines a library of exactly 80+ tools with their parameters, provides dozens of few-shot examples of correct JSON output, and includes the user's memory context (last project, recent commands). Nova Pro returns a structured JSON execution plan like this:

```json
{
  "intent": "prepare EduPulse development environment",
  "tasks": [
    { "tool": "open_project", "project": "EduPulse" },
    { "tool": "run_terminal", "command": "python manage.py runserver", "project": "EduPulse" },
    { "tool": "wait_for_server", "url": "http://localhost:8000" },
    { "tool": "open_browser", "url": "http://localhost:8000" }
  ]
}
```

The planner also classifies commands by complexity. Simple commands (open app, volume up, take screenshot) are routed to the faster and cheaper Nova Lite model, saving roughly 800ms per request. Complex multi-step commands (create project, compose email, code generation) use Nova Pro for reliability. Frequently repeated commands hit a 30-entry LRU cache and skip Bedrock entirely, returning the cached plan in under 5ms.

The system also detects sensitive operations (terminal commands, file deletion, email composition, system settings, shutdown) and sets a `requires_approval` flag. These plans pause at the approval gate in the UI — the user sees each step labeled "sensitive" and must explicitly click Approve before anything runs.

### 4. Execution (The Arms)

Once approved (or auto-approved for safe commands), the plan goes to `POST /execute`. The executor loops through each task and dispatches it to the appropriate controller. There are 25 controllers covering every aspect of the Windows desktop.

The executor is built as a registry — a dictionary mapping each of the 80+ tool names to an async handler function. Each handler knows exactly which controller function to call and how to extract the right parameters from the task dict. Between steps, the executor applies smart waits — for example, after opening an application, it polls the window title every 150ms until the app's window appears (up to 3 seconds) before moving to the next step that needs that app to be focused. This prevents typing into the wrong window or clicking before a page loads.

### 5. Voice Response

After execution, the backend generates a natural spoken response based on what was done. The response is spoken aloud via Amazon Polly (cloud) or pyttsx3 (local SAPI) as a non-blocking background call, so the UI updates immediately without waiting for speech to finish. The frontend animates a waveform for exactly as long as the speech plays, calculated from word count and speaking rate.

### 6. Memory and Credits

Every executed command is saved to both SQLite (local cache) and Amazon DynamoDB (cloud sync). DynamoDB stores per-user memory (last project, command history, credits) across sessions. The credits system deducts one credit per Bedrock planning call using a DynamoDB conditional update that atomically checks the balance before deducting — preventing race conditions and overdrafts. If DynamoDB is unreachable, the system falls back to SQLite and allows commands through, ensuring the agent works offline.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Electron Desktop App  (electron-app/)                          │
│                                                                 │
│  Full-window app built with Electron 31 + React 18 + Vite      │
│  Custom frameless window, system tray, single-instance lock     │
│                                                                 │
│  Panels: Voice | Files | Projects | Activity | Memory | Settings│
│  Context: AgentContext manages all API calls and state          │
│  IPC: contextBridge (contextIsolation:true, nodeIntegration:off)│
│  Spawns: FastAPI backend + wake-word listener as child processes │
└─────────────────────────────────────────────────────────────────┘
         │ HTTP REST + WebSocket  (localhost:8888)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (backend/)                                    │
│                                                                 │
│  Python 3.11 + FastAPI + Uvicorn                               │
│  ├── /transcribe    → faster-whisper local → Transcribe fallback│
│  ├── /plan          → enhance → enrich memory → Bedrock → cache │
│  ├── /execute       → registry dispatch → 25 controllers        │
│  ├── /files/*       → SQLite file index + watchdog watcher      │
│  ├── /projects      → project registry                          │
│  ├── /memory        → DynamoDB context                          │
│  ├── /credits       → DynamoDB credits                          │
│  ├── /auth/*        → DynamoDB user accounts                    │
│  └── /ws            → WebSocket for real-time execution updates │
└─────────────────────────────────────────────────────────────────┘
         │ boto3 SDK
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  AWS Services                                                   │
│                                                                 │
│  Amazon Bedrock Nova Pro   → main AI planner                    │
│  Amazon Bedrock Nova Lite  → prompt enhancer + simple commands  │
│  Amazon Transcribe         → voice-to-text fallback             │
│  Amazon Polly              → text-to-speech responses           │
│  Amazon DynamoDB           → user accounts, memory, credits     │
│  Amazon S3                 → audio file uploads + .exe hosting  │
│  Amazon Textract           → screen OCR (screen_reader feature) │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Vercel Web App  (web/)                                         │
│                                                                 │
│  React 18 + Vite, deployed to Vercel                           │
│  Landing page: hero, demo, features, download button → S3 .exe │
│  Dashboard: credits balance, command history, buy credits       │
│  Auth: connects to local backend for login/signup               │
│  WebSocket: connects to local agent for live status indicator   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack — In Detail

### Electron Desktop Application
The desktop app is built with Electron 31 and React 18 with JSX (no TypeScript). The window is completely frameless — a custom React TitleBar component handles minimize, maximize, and close. The main process (`electron/main.js`) spawns the Python FastAPI backend as a child process on startup, polls `/health` every second until the backend is ready, then signals the renderer. The entire Electron security model is followed: `contextIsolation: true`, `nodeIntegration: false`, and a minimal `contextBridge` in `preload.js` that exposes only a controlled `window.dp` API to the renderer. IPC channels are whitelisted.

The app uses a system tray with a context menu for quick actions (screenshot, mute, battery, show window, restart backend, quit). It enforces a single-instance lock so double-launching shows the existing window. The close button minimizes to tray rather than quitting — the Quit option in the tray menu is the only way to fully exit and stop the backend processes.

### FastAPI Backend
The backend is a Python 3.11 FastAPI application that serves as the local AI brain. On startup it initializes the SQLite database, indexes the file system (scans Desktop, Documents, Downloads, and other key directories for 24 file extensions up to 4 folders deep), starts a Watchdog file system watcher for incremental re-indexing, starts the clipboard monitor, and schedules a Bedrock connection pre-warm. All of this happens asynchronously so the backend is ready in under 3 seconds.

The executor is the core dispatch layer. It contains a registry of 118 tool handlers (a Python dict mapping each tool name to an async function). The `execute_task` function does a single dictionary lookup and calls the handler — no chains of if/elif statements. Each handler extracts the relevant parameters from the task dict and calls the appropriate controller function, running blocking operations (subprocess, file I/O) through `loop.run_in_executor` to keep the event loop free.

### Amazon Bedrock Integration
The integration uses boto3 to call Bedrock's `invoke_model` API directly. The planner builds its request body dynamically based on the detected model type — Amazon Nova uses the `messages-v1` schema, Anthropic Claude uses the `anthropic_version` schema, and Meta Llama uses the prompt format. This means the planner works with any Bedrock model just by changing the `BEDROCK_MODEL_ID` environment variable.

The latency pipeline runs in parallel: as soon as transcription finishes, an acknowledgment phrase ("Got it, Sir") is spoken immediately via non-blocking SAPI, and the Bedrock call begins. The user hears a response within 80ms while planning takes 400–1200ms in the background. Simple commands (open, close, volume, screenshot) are classified and routed to Nova Lite, saving 800ms per request. Repeated identical commands hit the LRU cache and skip Bedrock entirely.

### Voice Pipeline
The voice stack has two layers. For input, faster-whisper (a high-performance Python port of OpenAI's Whisper model) runs locally for instant offline transcription. Amazon Transcribe is the fallback for longer recordings or when local transcription is unavailable. For output, Amazon Polly provides high-quality neural TTS with the voice "Gregory" (professional English). pyttsx3/SAPI is the offline fallback. All voice output is non-blocking — the backend estimates speech duration from word count and returns `speech_ms` to the frontend so the waveform animation matches the actual speech length.

### Amazon DynamoDB
Three DynamoDB tables power the cloud layer. `DesktopPilotMemory` stores per-user context: the last project they worked on, their credit balance, and their last active timestamp. `DesktopPilotCommands` is an append-only log of every executed command with timestamps, intent, status (completed/failed/rejected), duration, and credits used — this powers the command history in the web dashboard. `CipherAIUsers` stores user accounts: email, hashed password, user ID, plan tier, and creation date. All DynamoDB writes use conditional expressions where appropriate (credit deduction uses `ConditionExpression` to atomically prevent negative balances) and all operations have exception handlers that fall back to SQLite so the agent works even when offline or when DynamoDB tables haven't been created yet.

### React Web Application
The web app is a standard React 18 + Vite SPA deployed on Vercel. It has three pages: a landing page with a feature showcase and download button, a user dashboard with credits balance, command history, and pricing plans, and a docs page. The Navbar includes an agent connection indicator that pings `localhost:8888/health` every 10 seconds — if the user's local agent is running, a green dot appears. A WebSocket connection to `ws://localhost:8888/ws` streams live execution updates to the dashboard in real time.

### Local Database (SQLite)
SQLite via Python's stdlib `sqlite3` serves as the local cache and offline store. Three tables: `files` (indexed file paths for fast search), `commands` (local command history), and `projects` (registered project registry with name, path, framework, and start command). All queries are fully parameterized — no string interpolation — preventing SQL injection. The file indexer runs Watchdog to watch for file system changes and debounces updates with a 2-second timer to avoid thrashing the database on bulk file operations.

### Desktop Controllers
The 25 controllers use a combination of Windows-specific libraries. `pyautogui` handles keyboard input, mouse movements, and screenshots. `pywin32` (`win32api`, `win32gui`, `win32con`) handles window management, focus detection, and system-level operations. `subprocess` with explicit argument arrays (never `shell=True` with user input) opens applications, runs terminal commands, and launches VS Code. The browser controller uses both the subprocess `start` command for quick URL opens and Playwright (via CDP connection to the user's existing Chrome) for full browser automation — clicking, typing, form filling, and page reading. Screen reading uses a Pillow screenshot piped to Amazon Textract for OCR. Windows Settings are opened via `ms-settings:` URIs covering 25+ setting categories.

---

## Features

### Voice and AI
- Wake word detection — say "Hey Cipher" to activate hands-free
- Voice-to-text via faster-whisper (local, offline) with Amazon Transcribe fallback
- AI planning via Amazon Bedrock Nova Pro — converts natural language to structured execution plans
- Prompt enhancement via Nova Lite — clarifies vague commands before planning
- LRU command cache — repeat commands skip Bedrock entirely
- Voice responses via Amazon Polly — speaks results naturally with waveform animation
- Knowledge questions — "What is machine learning?" answered by Bedrock and spoken aloud

### Desktop Automation
- Open any Windows application by name (20+ registered, Windows Search fallback)
- Full browser automation via Playwright — navigate, click, type, fill forms, read pages
- File operations — copy, move, rename, delete, zip, unzip, find duplicates, cleanup Desktop
- Project scaffolding — Vite, Next.js, React, Django, FastAPI, Angular, Vue, Svelte, Flask
- Terminal commands — run CLI commands in visible CMD windows with safety filtering
- Windows Settings — 25+ ms-settings: URIs
- Window management — snap, minimize, maximize, close, switch, list open windows
- Screen reading — OCR via Amazon Textract
- System info — battery, RAM, CPU, IP address, disk usage, Wi-Fi info
- System maintenance — recycle bin, DNS flush, disk cleanup, port checker, startup programs
- Clipboard management — history, smart paste, AI query on clipboard content
- Meeting assistant — record meetings, transcribe, extract action items, generate .docx notes
- Focus mode — Pomodoro timer with distraction blocking
- Smart reply — AI-generated replies typed into the active window
- Brightness and volume control
- Timers and screenshots
- WhatsApp Web automation

### Developer Experience
- Project registry — register local projects with name, path, framework, start command
- Auto-discovery — scans for `package.json`, `manage.py`, `requirements.txt`, `pyproject.toml`
- One command to open project + start server + open browser
- Code generation — write, save, and execute code in Python, JavaScript, Java, C
- File creation — AI-generated .docx, .pptx, .xlsx documents

---

## Project Structure

```
DesktopPilot/
├── backend/
│   ├── main.py                      ← FastAPI app, all routes, WebSocket, lifespan
│   ├── requirements.txt
│   ├── .env.example
│   ├── ai/
│   │   ├── planner.py               ← Bedrock Nova Pro → JSON plan, model routing
│   │   ├── prompt_enhancer.py       ← Nova Lite → clarify vague commands
│   │   ├── memory.py                ← DynamoDB context, credits, command history
│   │   └── content_generator.py    ← Rich content for docs/pptx generation
│   ├── automation/
│   │   └── executor.py             ← Registry dispatch (118 tool handlers)
│   ├── controllers/                ← 25 domain controllers
│   ├── database/
│   │   └── sqlite_manager.py       ← SQLite CRUD for files, commands, projects
│   ├── indexer/
│   │   └── file_indexer.py         ← File system scan + Watchdog watcher
│   └── voice/
│       ├── transcriber.py          ← faster-whisper local + Transcribe fallback
│       ├── pipeline.py             ← LRU cache, model routing, parallel ack
│       └── wake_listener.py        ← Always-on wake word detection
│
├── electron-app/
│   ├── electron/
│   │   ├── main.js                 ← Main process: window, tray, Python spawn, IPC
│   │   └── preload.js              ← contextBridge: window.dp API
│   └── src/
│       ├── App.jsx                 ← Panel routing, auth state
│       ├── context/AgentContext.jsx← All API calls, backend state, WebSocket
│       ├── panels/                 ← Voice, Files, Projects, Activity, Memory, Settings
│       └── components/             ← TitleBar, Sidebar, StatusBar
│
└── web/
    └── src/
        ├── pages/                  ← LandingPage, Dashboard, DocsPage, LoginPage
        ├── components/             ← Navbar
        └── context/AuthContext.jsx ← Auth state, login/signup
```

---

## Prerequisites

- **Windows 10 or 11**
- **Python 3.11+** — [python.org](https://www.python.org/downloads/) — tick "Add Python to PATH" during install
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **AWS Account** with the following services enabled:
  - Amazon Bedrock — enable Nova Pro (`us.amazon.nova-pro-v1:0`) and Nova Lite (`us.amazon.nova-lite-v1:0`) in the model access console
  - Amazon Transcribe — no special setup needed
  - Amazon DynamoDB — create the three tables listed below
  - Amazon S3 — create a bucket for audio uploads
  - Amazon Polly — no special setup needed

---

## Setup

### 1. Clone

```bash
git clone https://github.com/Cyberexe1/DesktopPilot-AI.git
cd DesktopPilot-AI
```

### 2. Backend

```bash
cd DesktopPilot/backend
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env`:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

S3_BUCKET_NAME=desktoppilot-audio
DYNAMODB_TABLE_MEMORY=DesktopPilotMemory
DYNAMODB_TABLE_COMMANDS=DesktopPilotCommands

BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
BEDROCK_ENHANCER_MODEL_ID=us.amazon.nova-lite-v1:0

WHISPER_MODEL=base
WAKE_WORD_MODEL=hey_jarvis
WAKE_WORD_THRESHOLD=0.5
```

Start the backend:

```bash
uvicorn main:app --port 8888
```

Verify: [http://localhost:8888/health](http://localhost:8888/health)

### 3. Desktop App

```bash
cd DesktopPilot/electron-app
npm install
npm run dev
```

The Electron app starts and automatically connects to the backend on port 8888.

### 4. Web App (optional for local dev)

```bash
cd DesktopPilot/web
npm install
copy .env.example .env
npm run dev
# http://localhost:3000
```

---

## AWS DynamoDB Setup

Create these three tables in your AWS region (us-east-1 recommended):

| Table Name | Partition Key | Sort Key |
|---|---|---|
| `DesktopPilotMemory` | `user_id` (String) | — |
| `DesktopPilotCommands` | `user_id` (String) | `timestamp` (String) |
| `CipherAIUsers` | `email` (String) | — |

The backend gracefully falls back to SQLite if these tables don't exist, so the agent works even without DynamoDB.

### IAM Permissions Required

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "transcribe:StartTranscriptionJob",
    "transcribe:GetTranscriptionJob",
    "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query",
    "s3:PutObject", "s3:GetObject",
    "polly:SynthesizeSpeech",
    "textract:DetectDocumentText", "textract:AnalyzeDocument"
  ],
  "Resource": "*"
}
```

---

## Build the Installer

```bash
cd DesktopPilot/electron-app
npm run build:win
# Produces: dist-electron/DesktopPilot AI Setup 1.0.1.exe
```

---

## Approval Gate

Sensitive operations pause and show an approval dialog before executing. The user sees each planned step labeled "sensitive" and must click Approve.

| Requires Approval | Auto-Executes |
|---|---|
| Terminal commands | Open applications |
| File delete / move | Open browser / URLs |
| Email compose | File search and open |
| System settings | Screenshots |
| Project creation | System info queries |
| Shutdown / restart | Volume / brightness |
| Desktop cleanup | Window management |

---

## Credits System

Each AI planning call costs 1 credit, deducted atomically from DynamoDB.

| Plan | Credits | Price |
|---|---|---|
| Free | 100 | $0 |
| Starter | 500 | $4.99 |
| Pro | 2,000 | $14.99 |
| Team | 10,000 | $39.99 |

---

## Example Commands

| Category | Example |
|---|---|
| Developer workflow | "Open my EduPulse project, start the server, and open it in browser" |
| Project creation | "Create a Vite React project called Dashboard on D drive" |
| File management | "Copy all PDF files from Downloads to D:/Reports" |
| Browser | "Open Gmail in Chrome", "Search YouTube for Python tutorials" |
| System | "How much battery do I have?", "Check which ports are in use" |
| Settings | "Open Bluetooth settings", "Open display settings" |
| Questions | "What is machine learning?", "Explain how DNS works" |
| Meeting | "Start recording my standup meeting" |
| Code | "Write a Python script that generates a Fibonacci sequence and run it" |
| Smart reply | "Write a professional reply to this email" |

See [PROMPTS.md](DesktopPilot/PROMPTS.md) for 200+ example commands.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `spawn python ENOENT` on launch | Python not on PATH — reinstall Python and tick "Add to PATH" |
| Backend shows "Starting…" forever | Check Task Manager for a crashed `python.exe`, restart the app |
| Bedrock access denied | Enable Nova Pro and Nova Lite in the AWS Bedrock model access console |
| DynamoDB errors | Create the three tables listed above, or the agent will work offline via SQLite |
| Port 8888 already in use | Run `netstat -ano \| findstr :8888` and kill the process using that port |
| Mic not working | Grant microphone permission in Windows Settings → Privacy → Microphone |

---

## License

MIT

---

## Built For

**AWS Hackathon** — Track 2 (B2B) / Track 4 (Open Innovation)

Powered by Amazon Bedrock · Amazon Transcribe · Amazon Polly · Amazon DynamoDB · Amazon S3 · Amazon Textract
