---
inclusion: always
---

# DesktopPilot AI — Project Steering Document

## What This Project Is

DesktopPilot AI is an autonomous voice-controlled desktop agent for Windows. Users speak natural language commands and the system plans, approves, and executes multi-step actions across their desktop — opening apps, managing files, launching dev environments, automating browsers, and controlling system settings.

Built for a hackathon under **Track 2 (B2B)** or **Track 4 (Open Innovation)**.

---

## Hackathon Hard Requirements

| Requirement | Solution |
|---|---|
| Frontend on Vercel | React + Vite (JSX) web app deployed to Vercel |
| AWS Database | Amazon DynamoDB (DesktopPilotMemory + DesktopPilotCommands) |
| Desktop agent distribution | `.exe` installer hosted on S3, download link on Vercel landing page |

---

## Two-Product Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCT 1 — Vercel Website  (web/)                             │
│                                                                 │
│  ├── Landing page                                               │
│  │     ├── Hero + features                                      │
│  │     ├── Download for Windows button → S3 .exe URL            │
│  │     └── How it works                                         │
│  │                                                              │
│  └── User Dashboard (/dashboard)                                │
│        ├── Credits balance + usage bar                          │
│        ├── Buy credits (3 pricing plans)                        │
│        ├── Command history (Phase 3: from DynamoDB)             │
│        └── Download card                                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PRODUCT 2 — Electron Desktop App  (electron-app/)  ← MAIN     │
│                                                                 │
│  Full-window app (like Kiro / VS Code) with:                    │
│                                                                 │
│  TitleBar  [DesktopPilot AI] [Agent Ready ●] [⚡ credits] [─□✕] │
│  ├── Sidebar navigation                                         │
│  │     🎤 Voice     — mic, transcript, plan, execution tracker  │
│  │     📁 Files     — searchable file browser, open files       │
│  │     🌿 Projects  — register/launch/open projects in VS Code  │
│  │     🕐 Activity  — command history + backend logs tabs       │
│  │     🧠 Memory    — last project, recent commands context     │
│  │     ⚙  Settings  — AWS config, approval toggles, links       │
│  │     ↗  Dashboard — opens Vercel web dashboard                │
│  └── StatusBar  [● FastAPI :8000]  [Windows]  [v1.0.0]         │
│                                                                 │
│  Internally spawns + manages FastAPI backend process            │
│  System tray — minimize to tray, stays running                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  LOCAL BACKEND  (backend/)                                      │
│                                                                 │
│  FastAPI on :8000 — spawned by Electron on startup             │
│  ├── /health          → agent status check                      │
│  ├── /transcribe      → upload audio → AWS Transcribe           │
│  ├── /plan            → text → AWS Bedrock → JSON plan          │
│  ├── /execute         → run plan through controllers            │
│  ├── /files/search    → query SQLite file index                 │
│  ├── /files/open      → open file with os.startfile             │
│  ├── /projects        → list / register projects                │
│  └── /memory          → context + command history               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  AWS BACKEND  (aws/)                                            │
│                                                                 │
│  Amazon Transcribe    → speech to text                          │
│  Amazon Bedrock       → Claude 3 Sonnet — intent + planning     │
│  AWS Lambda           → voice-handler, planner-handler,         │
│                          memory-handler, executor-handler        │
│  AWS Step Functions   → full pipeline orchestration             │
│  Amazon DynamoDB      → cloud memory + command history          │
│  Amazon S3            → audio uploads + .exe installer          │
│  Amazon CloudWatch    → structured logs + metrics               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Vercel Website | React 18 + Vite 5 + JSX, react-router-dom, lucide-react |
| Desktop App | Electron 31 + React 18 + JSX (Vite renderer) |
| Local Backend | Python 3.11 + FastAPI 0.111 + Uvicorn |
| AI Planning | Amazon Bedrock — Claude 3 Sonnet |
| Voice Input | Amazon Transcribe |
| Orchestration | AWS Step Functions + AWS Lambda |
| Cloud Database | Amazon DynamoDB |
| Local Database | SQLite (via sqlite3 stdlib) |
| File Storage | Amazon S3 |
| Browser Automation | subprocess + Windows `start` command (Phase 1), Playwright (Phase 2) |
| Desktop Control | subprocess + os.startfile + pywin32 |
| Monitoring | Amazon CloudWatch |
| Installer Build | electron-builder → NSIS .exe |

---

## Actual Folder Structure (as built)

```
DesktopPilot/
│
├── web/                              ← Vercel website
│   ├── index.html
│   ├── vite.config.js
│   ├── vercel.json                   ← SPA rewrite rules
│   ├── package.json
│   ├── .env.example
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                   ← Routes: / /dashboard /docs
│       ├── index.css                 ← Global design tokens + utilities
│       ├── pages/
│       │   ├── LandingPage.jsx + .css
│       │   ├── Dashboard.jsx + .css  ← Credits, billing, history
│       │   └── DocsPage.jsx + .css
│       ├── components/
│       │   └── Navbar.jsx + .css     ← Agent connection indicator
│       └── lib/
│           ├── api.js                ← transcribeAudio, generatePlan, executePlan
│           └── websocket.js          ← ws://localhost:8765 client
│
├── electron-app/                     ← Desktop app (.exe)
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── electron/
│   │   ├── main.js                   ← Main process: window, tray, FastAPI spawn, IPC
│   │   └── preload.js                ← contextBridge: window.dp API
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                   ← AgentProvider + AppShell + panel routing
│       ├── context/
│       │   └── AgentContext.jsx      ← All API calls, backend state, addLog
│       ├── styles/
│       │   ├── global.css            ← CSS variables, reset, utilities
│       │   └── app.css               ← Panel, card, button, input, badge styles
│       ├── components/
│       │   ├── TitleBar.jsx + .css   ← Frameless title bar, window controls
│       │   ├── Sidebar.jsx + .css    ← Nav items with active indicator
│       │   └── StatusBar.jsx + .css  ← Backend status + version
│       └── panels/
│           ├── VoicePanel.jsx + .css     ← Full voice → plan → approve → execute flow
│           ├── FilesPanel.jsx + .css     ← File search + open
│           ├── ProjectsPanel.jsx + .css  ← Register/launch/open projects
│           ├── ActivityPanel.jsx + .css  ← Commands + backend logs tabs
│           ├── MemoryPanel.jsx + .css    ← Context viewer
│           └── SettingsPanel.jsx + .css  ← AWS config, toggles, links
│
├── backend/                          ← FastAPI local agent
│   ├── main.py                       ← All routes + lifespan startup
│   ├── requirements.txt
│   ├── .env.example
│   ├── ai/
│   │   ├── planner.py                ← Bedrock Claude → JSON plan + approval flag
│   │   └── memory.py                 ← Context enrichment for prompts
│   ├── controllers/
│   │   ├── app_controller.py         ← 20+ Windows apps registry
│   │   ├── browser_controller.py     ← open_url, search_web, open_gmail_compose
│   │   ├── file_controller.py        ← Search SQLite index + os.startfile
│   │   ├── terminal_controller.py    ← run_in_terminal, open_vscode (safety checked)
│   │   └── settings_controller.py   ← 25+ ms-settings: URIs
│   ├── indexer/
│   │   └── file_indexer.py           ← Scans 6 dirs, depth 4, 20 extensions
│   ├── database/
│   │   └── sqlite_manager.py         ← Full CRUD: files, commands, projects
│   ├── automation/
│   │   └── executor.py               ← Async multi-step plan runner
│   └── voice/
│       └── transcriber.py            ← S3 upload → Transcribe job → poll → text
│
└── aws/                              ← Phase 3 cloud resources
    ├── lambda/
    │   ├── voice_handler/
    │   ├── planner_handler/
    │   └── memory_handler/
    └── stepfunctions/
        └── workflow.json
```

---

## Development Phases

### Phase 1 — Foundation ✅ COMPLETE
**What was built:**
- Electron app: full-window Kiro-style layout (TitleBar, Sidebar, 6 panels, StatusBar)
- Electron main process: spawns FastAPI, system tray, IPC handlers, window controls
- FastAPI backend: all routes live (`/health`, `/transcribe`, `/plan`, `/execute`, `/files/*`, `/projects`, `/memory`)
- Voice pipeline: mic → MediaRecorder → FormData → `/transcribe` → AWS Transcribe → text
- AI planner: text → `/plan` → Bedrock Claude 3 Sonnet → JSON plan with `requires_approval` flag
- Executor: async multi-step runner dispatching to all 5 controllers
- SQLite: files, commands, projects tables initialized on startup
- File indexer: runs on startup, scans 6 directories, 20 file extensions
- All 5 controllers: app, browser, file, terminal, settings
- Vercel web app: landing page, credits dashboard, docs page

### Phase 2 — Intelligence (Next)
**What to build:**
- Playwright browser automation (replace subprocess `start` with full Playwright control)
- Watchdog file watcher (re-index on file changes, not just startup)
- DynamoDB integration in memory layer (replace SQLite-only memory with cloud sync)
- Credits system: deduct credits per Bedrock call, enforce limit
- WebSocket real-time streaming (stream execution steps to web dashboard)
- Project auto-discovery (scan for package.json, manage.py, requirements.txt)
- Notification system (Windows toast notifications on completion)

### Phase 3 — AWS Cloud + Production (Final)
**What to build:**
- Lambda functions: voice-handler, planner-handler, memory-handler, executor-handler
- Step Functions state machine: full pipeline orchestration with approval wait
- DynamoDB tables: DesktopPilotMemory + DesktopPilotCommands (create + wire up)
- S3 audio pipeline: upload from Electron → trigger Lambda → Transcribe
- CloudWatch: structured logging from all Lambda functions + custom metrics
- electron-builder: build `.exe` installer, upload to S3, update Vercel download URL
- Vercel dashboard: wire command history to real DynamoDB data via API route
- IAM roles + policies for all services

---

## Database Schema

### DynamoDB — DesktopPilotMemory
```
PK: user_id (String)
Attributes:
  last_command       String
  last_project       Map { name, path, framework, start_command }
  favorite_projects  List<String>
  credits_remaining  Number
  last_updated       String (ISO 8601)
```

### DynamoDB — DesktopPilotCommands
```
PK: user_id (String)
SK: timestamp (String, ISO 8601)
Attributes:
  command     String
  intent      String
  plan        Map
  status      String  (completed | failed | rejected)
  duration_ms Number
  credits_used Number
```

### SQLite — Local Cache (desktoppilot.db)
```sql
CREATE TABLE files (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  path          TEXT NOT NULL,
  modified_date TEXT
);

CREATE TABLE commands (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  command   TEXT NOT NULL,
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE projects (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  path          TEXT NOT NULL,
  framework     TEXT,
  start_command TEXT
);
```

---

## AI Planner — Tool Reference

The Bedrock prompt must only use these exact tool names:

| Tool | Required Params | Optional Params |
|---|---|---|
| `open_application` | `name` | — |
| `open_project` | `project` | — |
| `run_terminal` | `command` | `project` |
| `wait_for_server` | `url` | — |
| `open_browser` | `url` | — |
| `search_web` | `query` | — |
| `open_file` | `name` | — |
| `open_setting` | `name` | — |
| `compose_email` | `to`, `subject` | `body` |

Planner always returns **valid JSON only** — no prose, no markdown fences.

---

## Approval Rules

**Requires approval (sensitive):**
- `run_terminal`
- `compose_email`
- `delete_file`
- `open_setting`

**Auto-executes (safe):**
- `open_application`, `open_browser`, `open_file`, `open_project`, `search_web`, `wait_for_server`

---

## Environment Variables

### backend/.env
```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=desktoppilot-audio
DYNAMODB_TABLE_MEMORY=DesktopPilotMemory
DYNAMODB_TABLE_COMMANDS=DesktopPilotCommands
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
STEP_FUNCTION_ARN=arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:DesktopPilotWorkflow
```

### web/.env
```env
VITE_API_URL=http://localhost:8000
VITE_DOWNLOAD_URL=https://desktoppilot-audio.s3.amazonaws.com/DesktopPilot-Setup.exe
```

Never hardcode credentials. Never commit `.env` files.

---

## Coding Standards

- **Frontend/Electron:** React 18 + JSX. No TypeScript (JSX only per user preference).
- **Backend:** Python 3.11+. Black formatting. Type hints on all functions.
- **API shape:** All FastAPI responses return `{ status, data, error }`.
- **Error handling:** Every controller catches exceptions and returns a string — never raises to executor.
- **Security:** Never `shell=True` with user input. Blocked commands list in terminal_controller.
- **Async:** FastAPI routes are `async`. Blocking boto3 calls run in `loop.run_in_executor`.
- **Logging:** Python `logging` module, JSON-formatted. Lambda functions use structured JSON logs.
- **No hardcoded paths:** Use `os.environ.get("USERNAME")` for user-specific paths.

---

## Key Demo Scenarios (Must Work)

1. **Developer workflow** — *"Prepare my EduPulse development environment."*
   - `open_project(EduPulse)` → `run_terminal(python manage.py runserver)` → `wait_for_server(localhost:8000)` → `open_browser(localhost:8000)`

2. **File search** — *"Open my latest resume."*
   - File indexer finds most recent resume → `open_file` → opens in Word

3. **Context memory** — *"Open my project."*
   - Memory layer recalls last used project → opens automatically

4. **Browser automation** — *"Open Gmail and draft a project update."*
   - `compose_email` → approval gate → Gmail compose opens pre-filled

5. **Settings** — *"Open Bluetooth settings."*
   - `open_setting(bluetooth)` → `start ms-settings:bluetooth`

---

## What NOT to Do

- Do not use `shell=True` with raw user input
- Do not store AWS credentials in source code or commit `.env`
- Do not skip the approval gate for terminal, email, or settings actions
- Do not use Next.js — the web frontend is React + Vite + JSX only
- Do not add Phase 2/3 features before Phase 1 deliverables are verified
- Do not commit `node_modules/`, `__pycache__/`, `*.db`, `*.exe`, `.env`
- Do not use `npm run dev` or `uvicorn --reload` in production builds

---

## How to Run

```bash
# 1. Backend (required first)
cd DesktopPilot/backend
pip install -r requirements.txt
cp .env.example .env          # fill in AWS credentials
uvicorn main:app --port 8000

# 2. Electron app (dev mode)
cd DesktopPilot/electron-app
npm install
npm run dev                   # starts Vite + Electron together

# 3. Web app (dev mode)
cd DesktopPilot/web
npm install
cp .env.example .env
npm run dev                   # http://localhost:3000

# 4. Deploy web to Vercel
cd DesktopPilot/web
npx vercel --prod
```

---

## References

- Phase 1 guide: `README_PHASE1_FOUNDATION.md`
- Phase 2 guide: `README_PHASE2_INTELLIGENCE.md`
- Phase 3 guide: `README_PHASE3_AWS_PRODUCTION.md`
- Original brief: `awstext.txt`
