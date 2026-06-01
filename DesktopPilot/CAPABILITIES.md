# DesktopPilot AI — Full Capabilities List

Everything the agent can do right now via voice commands.

---

## 🖥️ Open Applications

| Command Example | What Happens |
|---|---|
| "Open Chrome" | Launches Google Chrome |
| "Open VS Code" | Launches Visual Studio Code |
| "Open Notepad" | Launches Notepad |
| "Open Word" | Launches Microsoft Word |
| "Open PowerPoint" | Launches Microsoft PowerPoint |
| "Open Excel" | Launches Microsoft Excel |
| "Open File Explorer" | Opens Windows Explorer |
| "Open Calculator" | Opens Calculator |
| "Open Task Manager" | Opens Task Manager |
| "Open Spotify" | Opens Spotify |
| "Open Discord" | Opens Discord |

**Supported apps:** Chrome, VS Code, Notepad, Word, Excel, PowerPoint, Explorer, Calculator, Paint, CMD, PowerShell, Terminal, Spotify, Discord, Slack, Zoom

---

## 📁 File Operations

### Create Files (any type)

| Command Example | What Happens |
|---|---|
| "Create a text file called notes.txt" | Creates on Desktop, opens in Notepad |
| "Create a Word document called report.docx" | Creates proper .docx, opens in Word |
| "Create a PowerPoint called presentation.pptx" | Creates proper .pptx with slides, opens in PowerPoint |
| "Create an Excel file called data.xlsx" | Creates proper .xlsx, opens in Excel |
| "Create an HTML file called index.html" | Creates file, opens in VS Code |
| "Create a Python file called app.py" | Creates file, opens in VS Code |
| "Create a JavaScript file called script.js" | Creates file, opens in VS Code |

### File Types & Where They Open

| Extension | Opens In | Format |
|---|---|---|
| `.txt`, `.log` | Notepad | Plain text |
| `.docx` | Microsoft Word | Proper OOXML document with paragraphs |
| `.pptx` | Microsoft PowerPoint | Proper presentation with slides + flowcharts |
| `.xlsx` | Microsoft Excel | Proper spreadsheet with rows/columns |
| `.html`, `.css`, `.js`, `.jsx`, `.ts`, `.tsx` | VS Code | Plain text (code) |
| `.py`, `.java`, `.cpp`, `.c` | VS Code | Plain text (code) |
| `.json`, `.md`, `.yaml`, `.xml`, `.sql` | VS Code | Plain text |
| `.pdf`, `.png`, `.jpg` | Default app | System default viewer |

### Search & Open Existing Files

| Command Example | What Happens |
|---|---|
| "Open my latest resume" | Searches file index → opens most recent match |
| "Find my DAA notes PDF" | Searches for "DAA" in indexed files |
| "Open project.py" | Finds and opens with default app |

### Write Content to Files

| Command Example | What Happens |
|---|---|
| "Create letter.txt and write a leave application" | Creates file with AI-generated letter content |
| "Create report.docx with a project status report" | Creates Word doc with full report |
| "Create presentation.pptx about Smart Agriculture" | Creates PowerPoint with title + content slides |
| "Create data.xlsx with student marks" | Creates Excel with data in rows/columns |

---

## ⌨️ Live Typing (Visual)

| Command Example | What Happens |
|---|---|
| "Open Notepad and write a letter to my boss" | Opens Notepad → types letter character by character (visible) |
| "Type: Hello World" | Types exact text into active window |
| "Press Ctrl+S" | Saves the current file |
| "Press Enter" | Presses Enter key |
| "Press Alt+F4" | Closes active window |

**You see the typing happen in real time** — characters appear one by one at human-like speed.

---

## 📊 PowerPoint Features

| Command Example | What Happens |
|---|---|
| "Create a presentation about AI" | Title slide + content slides with bullet points |
| "Create a pptx with a flowchart of software development" | Title slide + flowchart slide with colored boxes + arrows |
| "Create a presentation with steps for deploying an app" | Flowchart with process steps |

### Flowchart Support

When you mention "flowchart", "diagram", "process flow", or "steps:" — the AI creates a visual flowchart with:
- Colored rounded rectangle boxes
- Down arrows connecting each step
- Up to 6 steps per flowchart slide
- Different colors for each step (blue, green, purple, orange, red, cyan)

---

## 🌐 Browser Automation

| Command Example | What Happens |
|---|---|
| "Open Chrome" | Launches Chrome |
| "Open Google" | Opens google.com in browser |
| "Search for AWS Bedrock documentation" | Opens Google search results |
| "Open YouTube" | Opens youtube.com |
| "Open Gmail and compose email to john@gmail.com about meeting" | Opens Gmail compose with to/subject/body pre-filled |

---

## 📧 Email Composition

| Command Example | What Happens |
|---|---|
| "Compose email to john@gmail.com about project update" | Opens Gmail compose with fields filled |
| "Send email to team@company.com saying meeting at 3pm" | Opens compose with subject + body |
| "Draft email to boss about leave tomorrow" | Opens compose with AI-generated content |

**Fields auto-filled:** To, Subject, Body — opens in your default browser where you're logged into Gmail.

---

## 🛠️ Project Scaffolding

| Command Example | What Happens |
|---|---|
| "Create a Vite React project called my-app" | Scaffolds full Vite project → opens in VS Code |
| "Create a Next.js project called my-site" | Scaffolds Next.js structure → opens in VS Code |
| "Create a Node.js project called api-server" | Scaffolds Express app → opens in VS Code |
| "Create a Python project called backend" | Scaffolds FastAPI project → opens in VS Code |
| "Create an HTML website called portfolio" | Scaffolds HTML/CSS/JS → opens in VS Code |

### What gets created per framework:

**Vite/React:**
```
my-app/
├── package.json
├── index.html
├── vite.config.js
└── src/
    ├── main.jsx
    └── App.jsx
```

**Next.js:**
```
my-site/
├── package.json
└── app/
    ├── page.jsx
    └── layout.jsx
```

**Node.js/Express:**
```
api-server/
├── package.json
└── index.js
```

**Python/FastAPI:**
```
backend/
├── requirements.txt
├── main.py
└── README.md
```

**HTML/Static:**
```
portfolio/
├── index.html
├── style.css
└── script.js
```

---

## 💻 Terminal / Command Execution

| Command Example | What Happens |
|---|---|
| "Run npm install in my project" | Opens CMD in project directory → runs command |
| "Start the Django server" | Runs `python manage.py runserver` in project folder |
| "Run git status" | Opens terminal with git status output |

**Safety:** Dangerous commands (rm -rf, format, del /f) are blocked automatically.

---

## 🔧 Windows Settings

| Command Example | What Happens |
|---|---|
| "Open Bluetooth settings" | Opens ms-settings:bluetooth |
| "Open WiFi settings" | Opens ms-settings:network-wifi |
| "Open Display settings" | Opens ms-settings:display |
| "Open Sound settings" | Opens ms-settings:sound |
| "Open Windows Update" | Opens ms-settings:windowsupdate |

**Supported settings:** WiFi, Bluetooth, Display, Sound, Apps, Updates, Privacy, Storage, Power, Accounts, Notifications, Taskbar, Themes, Keyboard, Mouse, Camera, Microphone, Location, VPN, Proxy, Date/Time, Language, Region

---

## 🧠 Memory & Context

| Feature | How It Works |
|---|---|
| "Open my project" | Recalls your last used project automatically |
| Remembers recent commands | Uses last 5 commands to understand context |
| Project registry | Knows your project names, paths, frameworks |
| File index | Searches 371+ files across Desktop/Documents/Downloads |

---

## 🔐 Approval System

These actions **always ask for your approval** before executing:

| Action | Why |
|---|---|
| Terminal commands | Could modify system |
| Email composition | Sends on your behalf |
| File creation/writing | Modifies your filesystem |
| System settings | Changes system config |
| Typing into windows | Controls your keyboard |
| Key presses | Controls your keyboard |
| Project scaffolding | Creates multiple files |

Safe actions (open app, open browser, search, open file) execute **immediately** without asking.

---

## 📈 Credits System

| Feature | Detail |
|---|---|
| Each voice command | Costs 1 credit |
| Starting balance | 100 credits |
| Credits stored in | Amazon DynamoDB |
| Buy more | Via web dashboard at desktoppilot.vercel.app |

---

## 🔔 Notifications

- Windows toast notification when a command finishes executing
- Shows success/failure count
- Works on Windows 10 and 11

---

## 👁️ Screen Reading & OCR (Amazon Textract)

| Command Example | What Happens |
|---|---|
| "Read what's on my screen" | Captures full screen → Textract OCR → returns all visible text |
| "Read the active window" | Captures only the focused window → extracts text |
| "Analyze my screen" | Full analysis — text + form fields + table detection |
| "What does this error say?" | Reads error message visible on screen |
| "Read this PDF on screen" | Captures and extracts text from whatever is displayed |
| "What's on this webpage?" | Reads all visible text from the browser |

### How it works

```
Screenshot (PyAutoGUI) → PNG image → Amazon Textract → Extracted text
```

### Three modes

| Mode | API | What it captures |
|---|---|---|
| Full screen | `GET /screen/read?mode=full` | Everything visible on your monitor |
| Active window | `GET /screen/read?mode=window` | Only the focused/active application |
| Full analysis | `GET /screen/analyze` | Text + form key-value pairs + table detection |

### What Textract can extract

| Content Type | Supported |
|---|---|
| Plain text on screen | ✅ |
| Text in images/PDFs displayed on screen | ✅ |
| Form fields (labels + values) | ✅ |
| Tables (rows + columns) | ✅ |
| Handwritten text | ✅ (if visible on screen) |
| Text in any language | ✅ (Textract supports 100+ languages) |

### Use cases

- Read error messages without manually copying
- Extract text from a PDF displayed on screen
- Read content from a webpage
- Capture form data visible in any application
- Read text from images or screenshots

---

## ❌ What It CANNOT Do (Yet)

| Limitation | Reason |
|---|---|
| PowerPoint animations (fly-in, fade) | python-pptx library doesn't support it |
| SmartArt diagrams | Not supported by library |
| Edit existing Word/PowerPoint content | Would need to read + modify + save |
| Drag and drop | PyAutoGUI can but it's fragile |
| Login to websites | Requires stored credentials |
| Multi-monitor control | PyAutoGUI works on primary monitor only |
| Android/phone control | Not implemented (future enhancement) |

---

## 🏗️ Architecture

```
Voice Command → Amazon Transcribe → Llama 3.3 70B (Bedrock) → JSON Plan → Executor → Desktop Actions
                                                                                    ↕
                                                              Screen Reading ← Amazon Textract ← Screenshot
```

All processing happens via:
- **Amazon Transcribe** — speech to text
- **Amazon Bedrock (Llama 3.3 70B)** — intent detection + plan generation
- **Amazon Textract** — screen reading / OCR (captures screen → extracts all text)
- **Amazon DynamoDB** — memory + credits + command history
- **Amazon S3** — audio file storage + screenshot storage
- **Local Python controllers** — actual desktop execution (PyAutoGUI, subprocess, python-pptx, python-docx)
