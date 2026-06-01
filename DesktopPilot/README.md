# DesktopPilot AI

Autonomous voice-controlled desktop agent powered by AWS Bedrock, Transcribe, Lambda, DynamoDB, and Step Functions.

## Quick Start

### 1. Backend (local agent)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # fill in AWS credentials
uvicorn main:app --reload --port 8000
```

### 2. Frontend (web dashboard)

```bash
cd web
npm install
cp .env.example .env        # set VITE_API_URL
npm run dev                 # http://localhost:3000
```

### 3. Deploy frontend to Vercel

```bash
cd web
npx vercel --prod
```

## Project Structure

```
DesktopPilot/
├── web/          ← React + Vite frontend (deploy to Vercel)
├── backend/      ← FastAPI local agent (runs on user's machine)
├── electron-app/ ← Desktop installer (Phase 3)
└── aws/          ← Lambda functions + Step Functions (Phase 3)
```

## Phase Progress

- [x] Phase 1 — Foundation (voice → plan → execute basic actions)
- [ ] Phase 2 — Intelligence (file indexer, project registry, multi-step)
- [ ] Phase 3 — AWS Cloud (Lambda, Step Functions, DynamoDB, installer)

See `README_PHASE1_FOUNDATION.md`, `README_PHASE2_INTELLIGENCE.md`, `README_PHASE3_AWS_PRODUCTION.md` for detailed guides.
