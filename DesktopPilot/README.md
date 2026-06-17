# DesktopPilot AI

> Autonomous voice-controlled desktop agent for Windows — powered by Amazon Bedrock, AWS Transcribe, and Electron.

Speak a command. Watch your desktop respond.

---

## What Is It?

DesktopPilot AI is a full-stack desktop application that lets you control your Windows PC using natural language. You speak (or type) a command, an AI planner breaks it into steps, you approve if needed, and the agent executes — opening apps, managing files, running code, controlling browsers, sending messages, and more.

Built for the **AWS Hackathon — Track 2 (B2B) / Track 4 (Open Innovation)**.

---

## What's Inside

```
DesktopPilot/
├── electron-app/       Desktop app (.exe) — the main product
├── backend/            FastAPI local agent — spawned by Electron on startup
├── web/                Vercel website — landing page + credits dashboard
├── CAPABILITIES.md     Every feature documented in detail
├── PROMPTS.md          200+ example voice commands
└── README.md           This file
```

---

## Products

### 1. Electron Desktop App (`electron-app/`)

The main application. A full-window dark UI (black + red theme) with:

| Panel | What You Can Do |
|---|---|
| 🎤 **Voice** | Speak or type a command → AI plans → approve → execute |
| 📁 **Files** | Search and open any indexed file |
| 🌿 **Projects** | Register, launch, and open dev projects in VS Code |
| 🕐 **Activity** | Command history + live backend logs |
| 🧠 **Memory** | View context — last project, recent commands |
| ⚙️ **Settings** | AWS config, approval toggles, backend links |

The app spawns the FastAPI backend automatically on startup, shows live status in the title bar, and minimises to system tray.

---

### 2. FastAPI Backend (`backend/`)

Local Python server on port `8888`. All AI and desktop control lives here.

| Route | Purpose |
|---|---|
| `GET  /health` | Agent status check |
| `POST /transcribe` | Upload audio → AWS Transcribe → text |
| `POST /plan` | Text → Amazon Bedrock (Nova Pro) → JSON plan |
| `POST /execute` | Run a plan through all controllers |
| `GET  /files/search` | Query the SQLite file index |
| `POST /files/open` | Open a file with `os.startfile` |
| `GET  /projects` | List registered projects |
| `POST /projects` | Register a new project |
| `GET  /memory` | Context + recent command history |
| `WS   /ws` | WebSocket — streams execution steps live |

---

### 3. Vercel Web App (`web/`)

Deployed at [desktoppilot.vercel.app](https://desktoppilot.vercel.app)

| Page | Contents |
|---|---|
| `/` | Landing page — hero, features, download button |
| `/dashboard` | Credits balance, usage bar, buy credits, command history |
| `/docs` | Documentation and setup guide |

---

## What It Can Do

### Voice & AI Pipeline

- 🎤 Speech → text via **Amazon Transcribe**
- 💡 Vague commands clarified by **Nova Lite** (prompt enhancer)
- 🧠 Intent planning via **Amazon Bedrock Nova Pro** → structured JSON plan
- 🔊 Voice responses via **Amazon Polly**
- 🔑 Wake word detection — say *"Hey Cipher"* to activate hands-free

### Desktop Automation (20+ controllers)

| Category | Capabilities |
|---|---|
| **Apps** | Open 20+ registered apps + Windows Search fallback for any installed app |
| **Browser** | Open URLs, search the web, Gmail compose with pre-filled fields |
| **Files** | Create, copy, move, rename, delete, zip/unzip files and folders |
| **Projects** | Scaffold Vite, Next.js, Django, FastAPI, Express, Angular, Vue, Svelte |
| **Code** | Generate, save, and execute Python/JS/Java/C code from a voice command |
| **Terminal** | Run CLI commands in a visible terminal window |
| **Windows Settings** | 25+ `ms-settings:` URIs — Bluetooth, WiFi, Display, Sound, Updates, and more |
| **Window Management** | Snap, maximize, minimize, switch, close any window or process |
| **Screen Reading** | OCR via **Amazon Textract** — read text from anything on your screen |
| **Smart Form Fill** | Detect form fields on screen → fill from your saved profile automatically |
| **Typing** | Type text or press key combos into the active window |
| **System Info** | Battery, RAM, CPU, IP address, disk usage |
| **Maintenance** | Recycle bin, DNS flush, open ports, disk cleanup |
| **WhatsApp** | Find contact by name → type message → send via desktop app |
| **Notifications** | Windows toast notification on command completion |
| **Screenshots** | Capture and save screen |
| **Clipboard** | Read clipboard content |
| **Timers** | Start countdown timers |
| **Smart Reply** | AI-generated reply suggestions for emails/messages |
| **Brightness / Volume** | Adjust display brightness and system volume |

---

## Approval System

Sensitive actions pause for your approval before running. Safe actions execute instantly.

| Requires Approval | Auto-Executes |
|---|---|
| Terminal commands | Open applications |
| Email compose | Open URLs / search web |
| File delete / move | Open files |
| System settings changes | System info queries |
| Project scaffolding | Screenshots |
| Typing into windows | Window snapping |
| Shutdown / restart | Clipboard read |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop App | Electron 31 + React 18 + JSX (Vite) |
| Local Backend | Python 3.11 + FastAPI 0.111 + Uvicorn |
| AI Planning | Amazon Bedrock — Nova Pro |
| Prompt Enhancement | Amazon Bedrock — Nova Lite |
| Voice Input | Amazon Transcribe |
| Voice Output | Amazon Polly |
| Screen OCR | Amazon Textract |
| Cloud Database | Amazon DynamoDB |
| Local Database | SQLite |
| File Storage | Amazon S3 |
| Web Frontend | React 18 + Vite + JSX → Vercel |
| Desktop Control | PyAutoGUI + pywin32 + subprocess + Playwright |

---

## AWS Services Used

| Service | Used For |
|---|---|
| **Amazon Bedrock** (Nova Pro) | AI intent detection and execution plan generation |
| **Amazon Bedrock** (Nova Lite) | Prompt enhancement — clarifying vague commands |
| **Amazon Transcribe** | Converting voice recordings to text |
| **Amazon Polly** | Text-to-speech voice responses |
| **Amazon Textract** | OCR — reading text from screen screenshots |
| **Amazon DynamoDB** | Cloud memory, credits system, command history |
| **Amazon S3** | Audio file storage, screenshot storage, `.exe` hosting |

---

## Prerequisites

- Windows 10 or 11
- Python 3.11+
- Node.js 18+
- AWS account with the following enabled:
  - Bedrock — Nova Pro + Nova Lite models activated
  - Transcribe, Polly, Textract, DynamoDB, S3

---

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env   # fill in your AWS credentials
uvicorn main:app --port 8888
```

Verify: [http://localhost:8888/health](http://localhost:8888/health)

### Desktop App (dev)

```bash
cd electron-app
npm install
npm run dev
```

### Web App (dev)

```bash
cd web
npm install
copy .env.example .env
npm run dev   # http://localhost:3000
```

### Deploy Web to Vercel

```bash
cd web
npx vercel --prod
```

### Build Desktop Installer

```bash
cd electron-app
npm run build
# outputs DesktopPilot-Setup.exe in dist/
```

---

## Environment Variables

### `backend/.env`

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

S3_BUCKET_NAME=desktoppilot-audio
DYNAMODB_TABLE_MEMORY=DesktopPilotMemory
DYNAMODB_TABLE_COMMANDS=DesktopPilotCommands

BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
BEDROCK_ENHANCER_MODEL_ID=us.amazon.nova-lite-v1:0
```

### `web/.env`

```env
VITE_API_URL=http://localhost:8000
VITE_DOWNLOAD_URL=https://desktoppilot-audio.s3.amazonaws.com/DesktopPilot-Setup.exe
```

---

## AWS Setup Checklist

**DynamoDB** — create two tables in `us-east-1`:

| Table | Partition Key | Sort Key |
|---|---|---|
| `DesktopPilotMemory` | `user_id` (String) | — |
| `DesktopPilotCommands` | `user_id` (String) | `timestamp` (String) |

**Bedrock** — enable in the console:
- `us.amazon.nova-pro-v1:0`
- `us.amazon.nova-lite-v1:0`

**S3** — create bucket: `desktoppilot-audio`

**IAM** — your user/role needs:
```
bedrock:InvokeModel
transcribe:StartTranscriptionJob
transcribe:GetTranscriptionJob
textract:DetectDocumentText
textract:AnalyzeDocument
polly:SynthesizeSpeech
dynamodb:GetItem
dynamodb:PutItem
dynamodb:UpdateItem
s3:PutObject
s3:GetObject
```

---

## Example Commands

```
"Open Chrome and search for AWS Bedrock pricing"
"Create a Vite React project called my-dashboard on D drive"
"Copy my resume from Downloads to D drive"
"Open Bluetooth settings"
"How much battery do I have?"
"Snap VS Code to the left half"
"Send WhatsApp to Mom saying I'll be home at 8"
"Create a PowerPoint about machine learning with a flowchart"
"Read what's on my screen"
"Fill this form with my details"
"Run git status in my project"
"Start a 10 minute timer"
"Write a Python script that reads a CSV file and run it"
```

See [PROMPTS.md](PROMPTS.md) for 200+ examples across every category.

---

## Credits

| Plan | Credits | Price |
|---|---|---|
| Free | 100 | $0 |
| Starter | 500 | $4.99 / month |
| Pro | 2,000 | $14.99 / month |
| Team | 10,000 | $39.99 / month |

Each AI command costs 1 credit. Balance is stored in DynamoDB and visible in both the desktop app title bar and the web dashboard.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Port 8888 in use | `netstat -ano \| findstr :8888` → kill the PID |
| Bedrock access denied | Enable Nova Pro + Nova Lite in AWS Bedrock console |
| DynamoDB errors | Create tables in `us-east-1` or update region in `.env` |
| pyautogui not found | `pip install pyautogui` with Python 3.11 |
| Electron blank screen | Check port 5174 isn't used by another Vite dev server |
| Mic not detected | Allow microphone access in Windows Privacy settings |

---

## License

MIT — built for the AWS Hackathon.
