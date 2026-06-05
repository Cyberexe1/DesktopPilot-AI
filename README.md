# Cipher AI — Autonomous Voice-Controlled Desktop Agent

An AI-powered desktop assistant for Windows that executes natural language voice commands. Speak a command, review the plan, and watch it execute — opening apps, managing files, launching dev environments, automating browsers, and controlling system settings.

Built with **Amazon Bedrock (Nova Pro)**, **AWS Transcribe**, **DynamoDB**, **Electron**, and **FastAPI**.

---

## Demo

```
You: "Open D drive and create a Vite React project called Dashboard"

Cipher AI:
  ✓ Enhanced: "Create a Vite React project called Dashboard on D:/ drive"
  ✓ Plan: create_project(name="Dashboard", framework="vite", directory="D:/")
  ✓ Terminal opens → npm create vite → npm install → VS Code opens
  ✓ "Project scaffolded and opened in VS Code, Sir."
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Electron Desktop App (electron-app/)                        │
│  Full-window UI: Voice → Plan → Approve → Execute            │
│  React 18 + JSX │ Spawns FastAPI backend on startup          │
└──────────────────────────────────────────────────────────────┘
         │ HTTP + WebSocket (port 8888)
         ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Backend (backend/)                                   │
│  ├── Prompt Enhancer (Nova Lite) — clarifies vague commands  │
│  ├── AI Planner (Nova Pro) — generates JSON execution plan   │
│  ├── Executor — dispatches tasks to 10+ controllers          │
│  ├── File Indexer + Watcher — SQLite file search             │
│  └── Memory Layer — DynamoDB cloud sync                      │
└──────────────────────────────────────────────────────────────┘
         │ boto3
         ▼
┌──────────────────────────────────────────────────────────────┐
│  AWS Services                                                │
│  Amazon Bedrock (Nova Pro/Lite) │ Amazon Transcribe          │
│  Amazon DynamoDB │ Amazon S3 │ Amazon Polly                  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Vercel Web App (web/)                                       │
│  Landing page + Credits Dashboard + Docs                     │
│  Connects to local agent via WebSocket for live updates      │
└──────────────────────────────────────────────────────────────┘
```

---

## Features

### Voice & AI
- 🎤 Voice-to-text via Amazon Transcribe
- 🧠 AI planning via Amazon Bedrock (Nova Pro) — converts speech to executable steps
- 💡 Prompt Enhancer (Nova Lite) — clarifies vague commands before planning
- 🔊 Voice responses via Amazon Polly — speaks results naturally

### Desktop Automation
- 📂 Open any Windows application (20+ registered + Windows Search fallback)
- 🌐 Browser automation — open URLs, search web, Gmail compose
- 📁 File operations — copy, move, rename, delete, zip/unzip, find duplicates
- 💻 Terminal commands — run CLI commands in visible terminals
- ⚙️ Windows Settings — 25+ ms-settings: URIs
- 🪟 Window management — snap, minimize, maximize, switch, close
- 🖥️ Screen reading — OCR via Amazon Textract

### Developer Tools
- 🚀 Project scaffolding — Vite, Next.js, Django, FastAPI, Angular, Vue, Svelte
- 📝 Code generation — write, save, and run code in Python/JS/Java/C
- 📊 File creation — .docx, .pptx, .xlsx with AI-generated content

### System
- 🔋 System info — battery, RAM, CPU, IP, disk
- 🗑️ Maintenance — recycle bin, DNS flush, ports, disk cleanup
- ⏱️ Timers, screenshots, clipboard management
- 💳 Credits system — DynamoDB-backed usage tracking

---

## Prerequisites

- **Windows 10/11**
- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **AWS Account** with access to:
  - Amazon Bedrock (Nova Pro + Nova Lite models enabled)
  - Amazon Transcribe
  - Amazon DynamoDB
  - Amazon S3
  - Amazon Polly

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/DesktopPilot.git
cd DesktopPilot
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
```

Edit `backend/.env` with your AWS credentials:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

S3_BUCKET_NAME=desktoppilot-audio
DYNAMODB_TABLE_MEMORY=DesktopPilotMemory
DYNAMODB_TABLE_COMMANDS=DesktopPilotCommands

BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
BEDROCK_ENHANCER_MODEL_ID=us.amazon.nova-lite-v1:0
```

Start the backend:

```bash
uvicorn main:app --port 8888
```

Verify it's running: http://localhost:8888/health

### 3. Electron Desktop App

```bash
cd electron-app

# Install dependencies
npm install

# Start in development mode
npm run dev
```

This launches the full desktop app UI. It connects to the backend on port 8888.

### 4. Web App (Optional — for Vercel deployment)

```bash
cd web

# Install dependencies
npm install

# Configure environment
copy .env.example .env

# Start dev server
npm run dev
```

The web app runs on http://localhost:3000 and connects to your local backend.

---

## AWS Setup

### DynamoDB Tables

Create these two tables in us-east-1:

**DesktopPilotMemory**
- Partition key: `user_id` (String)

**DesktopPilotCommands**
- Partition key: `user_id` (String)
- Sort key: `timestamp` (String)

### Amazon Bedrock

Enable these models in the Bedrock console:
- `us.amazon.nova-pro-v1:0` (main planner)
- `us.amazon.nova-lite-v1:0` (prompt enhancer)

### S3 Bucket

Create a bucket named `desktoppilot-audio` for voice audio uploads.

### IAM Permissions

Your IAM user/role needs:
- `bedrock:InvokeModel`
- `transcribe:StartTranscriptionJob`, `transcribe:GetTranscriptionJob`
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`
- `s3:PutObject`, `s3:GetObject`
- `polly:SynthesizeSpeech`

---

## Project Structure

```
DesktopPilot/
├── backend/                    ← FastAPI local agent
│   ├── main.py                 ← All routes + WebSocket + lifespan
│   ├── requirements.txt
│   ├── .env.example
│   ├── ai/
│   │   ├── planner.py          ← Bedrock Nova Pro → JSON plan
│   │   ├── prompt_enhancer.py  ← Nova Lite → clarify vague commands
│   │   ├── memory.py           ← DynamoDB context + credits
│   │   └── content_generator.py← Rich content for docs/pptx
│   ├── automation/
│   │   └── executor.py         ← Dispatches tasks to controllers
│   ├── controllers/
│   │   ├── app_controller.py           ← Open 20+ Windows apps
│   │   ├── browser_controller.py       ← URLs, search, Gmail
│   │   ├── file_controller.py          ← File search + open
│   │   ├── file_writer_controller.py   ← Create files + projects
│   │   ├── file_ops_controller.py      ← Copy, move, rename, zip
│   │   ├── terminal_controller.py      ← Run CLI commands
│   │   ├── settings_controller.py      ← Windows settings
│   │   ├── keyboard_controller.py      ← Type text, press keys
│   │   ├── window_controller.py        ← Snap, minimize, switch
│   │   ├── screen_reader_controller.py ← OCR via Textract
│   │   ├── code_controller.py          ← Generate + run code
│   │   ├── knowledge_controller.py     ← Answer questions
│   │   ├── system_controller.py        ← Battery, RAM, CPU
│   │   ├── system_maintenance_controller.py ← Cleanup, DNS, ports
│   │   ├── whatsapp_controller.py      ← Send WhatsApp messages
│   │   ├── notification_controller.py  ← Windows toast notifications
│   │   ├── voice_output_controller.py  ← Amazon Polly TTS
│   │   ├── smart_reply_controller.py   ← AI-powered replies
│   │   ├── brightness_controller.py    ← Screen + volume control
│   │   └── utility_controller.py       ← Clipboard, timers, screenshots
│   ├── database/
│   │   └── sqlite_manager.py   ← Local SQLite (files, commands, projects)
│   ├── indexer/
│   │   └── file_indexer.py     ← Scan + watch file system
│   └── voice/
│       └── transcriber.py      ← S3 upload → Transcribe → text
│
├── electron-app/               ← Desktop app (.exe)
│   ├── electron/
│   │   ├── main.js             ← Main process: window, tray, FastAPI spawn
│   │   └── preload.js          ← contextBridge API
│   └── src/
│       ├── App.jsx             ← Panel routing
│       ├── context/AgentContext.jsx ← All API calls + state
│       ├── components/         ← TitleBar, Sidebar, StatusBar
│       └── panels/             ← Voice, Files, Projects, Settings, etc.
│
├── web/                        ← Vercel website
│   └── src/
│       ├── pages/              ← Landing, Dashboard, Docs
│       ├── components/         ← Navbar
│       └── lib/                ← API client + WebSocket
│
├── PROMPTS.md                  ← 200+ example voice commands
├── CAPABILITIES.md             ← Full feature documentation
└── README.md                   ← This file
```

---

## How It Works

```
User speaks: "Copy my resume from Downloads to D drive"
        │
        ▼
┌─ Prompt Enhancer (Nova Lite) ─────────────────────────┐
│ Input:  "Copy my resume from Downloads to D drive"    │
│ Output: "Copy my resume from Downloads to D drive"    │
│ (already clear — no enhancement needed)               │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌─ AI Planner (Nova Pro) ──────────────────────────────┐
│ Returns JSON:                                         │
│ {                                                     │
│   "intent": "copy resume to D drive",                │
│   "tasks": [{                                         │
│     "tool": "copy_file",                             │
│     "source": "resume",                              │
│     "destination": "D:/"                             │
│   }]                                                  │
│ }                                                     │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌─ Executor ────────────────────────────────────────────┐
│ 1. Searches file index for "resume"                   │
│ 2. Finds: C:\Users\...\Documents\Resume_2024.pdf     │
│ 3. Copies to D:/Resume_2024.pdf                      │
│ 4. Returns success message                            │
└───────────────────────────────────────────────────────┘
        │
        ▼
Voice: "File copied to D drive, Sir."
```

---

## Example Commands

| Category | Command |
|----------|---------|
| Apps | "Open Chrome", "Open VS Code", "Open Spotify" |
| Browser | "Open Gmail in Chrome", "Search for React docs" |
| Files | "Copy resume to D drive", "Zip my project folder" |
| Projects | "Create a Vite React project called my-app on D drive" |
| Terminal | "Run git status in my project" |
| Settings | "Open Bluetooth settings", "Open WiFi" |
| System | "How much battery?", "Check which ports are in use" |
| Email | "Compose email to john@gmail.com about meeting" |
| Code | "Create a Python script that prints fibonacci and run it" |
| Window | "Snap Chrome to the left", "Minimize everything" |
| Voice | "Hello Cipher", "What is machine learning?" |

See [PROMPTS.md](PROMPTS.md) for 200+ example commands.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop App | Electron 31 + React 18 + JSX (Vite) |
| Local Backend | Python 3.11 + FastAPI + Uvicorn |
| AI Planning | Amazon Bedrock — Nova Pro |
| Prompt Enhancement | Amazon Bedrock — Nova Lite |
| Voice Input | Amazon Transcribe |
| Voice Output | Amazon Polly |
| Cloud Database | Amazon DynamoDB |
| Local Database | SQLite |
| File Storage | Amazon S3 |
| Web Frontend | React 18 + Vite + JSX (Vercel) |
| Desktop Control | pyautogui + pywin32 + subprocess |

---

## Deployment

### Web App → Vercel

```bash
cd web
npx vercel --prod
```

### Desktop App → .exe Installer

```bash
cd electron-app
npm run build
# Produces DesktopPilot-Setup.exe in dist/
```

---

## Approval System

Sensitive commands require user approval before execution:

| Requires Approval | Auto-Executes |
|---|---|
| Terminal commands | Open applications |
| Email compose | Open browser/URLs |
| File delete/move | Open files |
| System settings | Search web |
| Project creation | System info queries |
| Shutdown/restart | Screenshots |
| Desktop cleanup | Window management |

---

## Credits System

Each AI command costs 1 credit (deducted from DynamoDB).

| Plan | Credits | Price |
|------|---------|-------|
| Free | 100 | $0 |
| Starter | 500 | $4.99/month |
| Pro | 2,000 | $14.99/month |
| Team | 10,000 | $39.99/month |

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Port 8888 in use | `netstat -ano \| findstr :8888` then kill the PID |
| pyautogui not found | `pip install pyautogui` (use Python 3.11 specifically) |
| Bedrock access denied | Enable Nova Pro/Lite models in AWS Bedrock console |
| DynamoDB errors | Create tables in us-east-1 or set region in .env |
| Electron shows wrong page | Check port 5174 isn't used by another Vite project |

---

## License

MIT

---

## Built For

AWS Hackathon — Track 2 (B2B) / Track 4 (Open Innovation)
