"""
DesktopPilot AI — Cloud API (AWS App Runner)

This is the CLOUD half of the split architecture. It exposes ONLY the
endpoints that are safe to run in a Linux container (no desktop, no display):

    /health            health check
    /plan              natural language -> JSON plan   (Amazon Bedrock)
    /transcribe        audio -> text                    (Amazon Transcribe)
    /memory            user context                     (DynamoDB)
    /memory/commands   recent command history
    /credits           credit balance
    /credits/buy       add credits
    /greet             greeting text (no local TTS in cloud)
    /auth/signup       create account                   (DynamoDB)
    /auth/login        authenticate

Desktop control (/execute, /files, voice output, screen reading, wake word)
stays in the LOCAL agent that ships inside the Electron installer.
"""

import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Cloud must never try to load the local Whisper model — force AWS Transcribe.
os.environ.setdefault("WHISPER_MODEL", "disabled")

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}'
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("DesktopPilot Cloud API starting up")
    # The memory layer falls back to local SQLite when a DynamoDB value is
    # missing, so ensure the (ephemeral) tables exist in the container.
    try:
        from database.sqlite_manager import init_db
        init_db()
    except Exception as e:
        log.warning(f"SQLite init skipped: {e}")
    yield
    log.info("DesktopPilot Cloud API shut down")


app = FastAPI(title="DesktopPilot AI — Cloud API", version="1.0.0", lifespan=lifespan)

# CORS — allow the Vercel site and the Electron app to call us.
ALLOWED = os.getenv("CORS_ALLOW_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED.split(",")] if ALLOWED != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(data):
    return {"status": "ok", "data": data, "error": None}

def err(message: str, code: int = 400):
    raise HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _build_greeting_text() -> str:
    """Time-aware greeting (cloud returns text only; the local agent speaks it)."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        period = "Good morning"
    elif 12 <= hour < 17:
        period = "Good afternoon"
    elif 17 <= hour < 21:
        period = "Good evening"
    else:
        period = "Hello"
    return f"{period}. DesktopPilot is ready. How can I help you today?"


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "DesktopPilot Cloud API v1.0.0"}


# ── Greeting ──────────────────────────────────────────────────────────────────

@app.post("/greet")
async def greet():
    return ok({"greeting": _build_greeting_text()})


# ── Plan ──────────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    text: str
    user_id: str = "default"

@app.post("/plan")
async def plan(req: PlanRequest):
    if not req.text.strip():
        err("Command text cannot be empty")

    from ai.memory import deduct_credits
    try:
        remaining = deduct_credits(req.user_id, amount=1)
    except ValueError as e:
        err(str(e), 402)
        return

    try:
        log.info(f"Planning: {req.text}")
        from ai.planner import generate_plan
        plan_data = await generate_plan(req.text, user_id=req.user_id)
        log.info(f"Plan: {len(plan_data.get('tasks', []))} tasks")

        # Persist the command to DynamoDB so the Memory/history view survives
        # across machines (the local desktop agent has no AWS credentials).
        try:
            from ai.memory import save_command_cloud
            save_command_cloud(
                user_id=req.user_id,
                command=req.text,
                intent=plan_data.get("intent", ""),
                status="planned",
                credits_used=1,
            )
        except Exception as e:
            log.warning(f"Command persist skipped: {e}")

        return ok({"plan": plan_data, "credits_remaining": remaining})
    except Exception as e:
        log.error(f"Planning error: {e}")
        err(str(e))


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        log.info(f"Received audio: {len(audio_bytes)} bytes")
        # Amazon Transcribe Streaming — no S3, ~1s latency.
        from voice.streaming_transcriber import transcribe_stream
        text = await transcribe_stream(audio_bytes, region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        log.info(f"Transcript: {text}")
        return ok({"text": text})
    except Exception as e:
        log.error(f"Transcription error: {e}")
        err(str(e))


# ── Memory ────────────────────────────────────────────────────────────────────

@app.get("/memory")
async def get_memory(user_id: str = "default"):
    from ai.memory import get_context
    try:
        return ok(get_context(user_id))
    except Exception as e:
        err(str(e))


@app.get("/memory/commands")
async def get_memory_commands(user_id: str = "default", limit: int = 25):
    from ai.memory import get_commands
    try:
        return ok({"commands": get_commands(user_id, limit)})
    except Exception as e:
        err(str(e))


# ── Credits ───────────────────────────────────────────────────────────────────

@app.get("/credits")
async def get_credits_route(user_id: str = "default"):
    from ai.memory import get_credits
    try:
        return ok({"credits_remaining": get_credits(user_id), "user_id": user_id})
    except Exception as e:
        err(str(e))


class BuyCreditsRequest(BaseModel):
    user_id: str
    plan: str

@app.post("/credits/buy")
async def buy_credits(req: BuyCreditsRequest):
    PLANS = {"starter": 500, "pro": 2000, "team": 10000}
    amount = PLANS.get(req.plan.lower())
    if not amount:
        err(f"Unknown plan: {req.plan}. Use: starter, pro, team")
    try:
        from ai.memory import _get_dynamo
        table = _get_dynamo().Table(os.getenv("DYNAMODB_TABLE_MEMORY", "DesktopPilotMemory"))
        response = table.update_item(
            Key={"user_id": req.user_id},
            UpdateExpression="SET credits_remaining = if_not_exists(credits_remaining, :zero) + :amount",
            ExpressionAttributeValues={":amount": amount, ":zero": 0},
            ReturnValues="UPDATED_NEW",
        )
        new_balance = int(response["Attributes"]["credits_remaining"])
        return ok({"plan": req.plan, "credits_added": amount, "credits_remaining": new_balance})
    except Exception as e:
        log.error(f"Buy credits failed: {e}")
        err(str(e))


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

@app.post("/auth/signup")
async def auth_signup(req: SignupRequest):
    from controllers.auth_controller import signup
    result = signup(req.name, req.email, req.password)
    if result["success"]:
        return ok(result)
    # A backend/DynamoDB failure is not a client error — surface it as 503.
    code = 503 if "Database error" in result.get("error", "") else 400
    err(result["error"], code)

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/login")
async def auth_login(req: LoginRequest):
    from controllers.auth_controller import login
    result = login(req.email, req.password)
    if result["success"]:
        return ok(result)
    # Distinguish backend failures (503) from bad credentials (401).
    code = 503 if "Database error" in result.get("error", "") else 401
    err(result["error"], code)
