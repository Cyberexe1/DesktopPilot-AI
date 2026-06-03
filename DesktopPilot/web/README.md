# Cipher AI — Web Application

React + Vite website deployed on Vercel. Serves as the landing page + user dashboard.

---

## Pages

### 1. Landing Page (`/`)

The public-facing homepage with:

- **Hero section** — "Your Desktop, Controlled by Voice" headline with gradient text
- **Download button** — "Download for Windows" linking to the .exe installer on S3
- **Open Dashboard** button — links to `/dashboard`
- **Terminal demo preview** — shows a simulated execution flow (open project → start server → open browser)
- **Features grid** (6 cards):
  - Voice Controlled
  - AI Planning
  - Multi-Step Execution
  - File Intelligence
  - Browser Automation
  - Safe by Design
- **How it works** (4 steps):
  1. Download & Install
  2. Speak a Command
  3. Review the Plan
  4. Watch it Execute
- **CTA section** — Download + Read Docs buttons
- **Footer** — AWS services used

---

### 2. Dashboard (`/dashboard`)

The user's control panel with 3 tabs:

#### Overview Tab
- **Credits Left** — shows remaining AI credits (from DynamoDB)
- **Commands Today** — count of commands run today
- **Plan** — current subscription tier (Free)
- **Recent Commands** — last 3 commands with timestamps
- **Desktop Agent card** — download button + description
- **Live Execution Feed** — shows real-time step updates when agent is running (via WebSocket)

#### Credits Tab
- **Usage bar** — visual bar showing credits used this month
- **3 Pricing Plans:**
  - Starter ($4.99/month) — 500 credits
  - Pro ($14.99/month) — 2,000 credits (Most Popular)
  - Team ($39.99/month) — 10,000 credits
- Each plan shows features + "Get Plan" button

#### History Tab
- **Command History** — full list of all commands with timestamps and credit usage
- **Refresh button** — pulls latest from backend
- **Agent status indicator** — shows "Live data" or "Agent offline"

---

### 3. Docs Page (`/docs`)

Setup guide with sidebar navigation:

1. Download & Install
2. Connect the Dashboard
3. Voice Commands
4. Approval Gate
5. Example Commands
6. Project Registry
7. AWS Services Used

---

## Components

### Navbar
- Logo: "Cipher AI" (was DesktopPilot)
- Navigation: Home | Dashboard | Docs
- **Agent connection indicator** — green dot + "Agent Connected" (pings `localhost:8000/health` every 10s)
- **Credits badge** — shows current balance when agent is online

---

## Real-Time Features

### WebSocket Connection
- Connects to `ws://localhost:8000/ws`
- Receives live events:
  - `execution_start` — shows live feed card
  - `step_update` — updates each step status (pending → done/failed)
  - `execution_done` — clears feed after 5 seconds
  - `plan_ready` — updates credits display

### Agent Polling
- Checks `/health` every 10 seconds
- When agent is online: fetches real credits from `/credits` and real history from `/memory/commands`
- When offline: shows cached/mock data

---

## Tech Stack

| Technology | Purpose |
|---|---|
| React 18 | UI framework |
| Vite 5 | Build tool + dev server |
| JSX | Component syntax (no TypeScript) |
| react-router-dom | Client-side routing |
| axios | HTTP client (web/src/lib/api.js) |
| lucide-react | Icons |

---

## Environment Variables

```env
# web/.env
VITE_API_URL=http://localhost:8000
VITE_DOWNLOAD_URL=https://your-s3-bucket.s3.amazonaws.com/CipherAI-Setup.exe
```

---

## Deployment

```bash
cd web
npm install
npm run build     # Builds to dist/
npx vercel --prod # Deploys to Vercel
```

### Vercel Config (`vercel.json`)
```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

SPA rewrite — all routes served by `index.html`.

---

## File Structure

```
web/
├── index.html
├── vite.config.js
├── vercel.json
├── package.json
├── .env.example
└── src/
    ├── main.jsx              ← Entry point
    ├── App.jsx               ← Routes: / /dashboard /docs
    ├── index.css             ← Global styles + CSS variables
    ├── pages/
    │   ├── LandingPage.jsx   ← Hero + features + how-it-works
    │   ├── LandingPage.css
    │   ├── Dashboard.jsx     ← Credits + billing + history + live feed
    │   ├── Dashboard.css
    │   ├── DocsPage.jsx      ← Setup guide
    │   └── DocsPage.css
    ├── components/
    │   ├── Navbar.jsx        ← Navigation + agent status
    │   └── Navbar.css
    └── lib/
        ├── api.js            ← API helpers (transcribe, plan, execute)
        └── websocket.js      ← WebSocket client for live updates
```

---

## Design

- Dark theme (CSS variables in `index.css`)
- Primary color: `#4f8ef7` (blue)
- Accent: `#7c5cfc` (purple)
- Responsive — works on mobile and desktop
- Clean, modern SaaS look
