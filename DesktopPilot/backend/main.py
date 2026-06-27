"""
DesktopPilot AI — FastAPI Backend (Phase 2)
"""

import logging
import os
import asyncio
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # Must be FIRST — before any module that reads env vars

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database.sqlite_manager import init_db
from indexer.file_indexer import index_files, start_file_watcher, stop_file_watcher, auto_register_projects
from voice.transcriber import transcribe_audio_bytes
from ai.planner import generate_plan
from automation.executor import execute_task

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}'
)
log = logging.getLogger(__name__)


# ── WebSocket manager ─────────────────────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        log.info(f"WS client connected. Total: {len(self._clients)}")

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)
        log.info(f"WS client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = WSManager()


# ── Lifespan ──────────────────────────────────────────────────────────────────

def _build_greeting_text() -> str:
    """Build a time-aware greeting using the user's name from their profile."""
    import json
    from datetime import datetime

    # Get user's first name from profile (fallback to "Sir")
    name = "Sir"
    try:
        profile_path = os.path.join(os.path.dirname(__file__), "user_profile.json")
        with open(profile_path, "r") as f:
            profile = json.load(f)
        first = (profile.get("first_name") or "").strip()
        full  = (profile.get("full_name") or "").strip()
        if first:
            name = first
        elif full and full.lower() != "john doe":
            name = full.split()[0]
    except Exception:
        pass

    # Time-aware greeting
    hour = datetime.now().hour
    if 5 <= hour < 12:
        period = "Good morning"
    elif 12 <= hour < 17:
        period = "Good afternoon"
    elif 17 <= hour < 21:
        period = "Good evening"
    else:
        period = "Hello"

    return f"{period}, {name}. DesktopPilot is ready. How can I help you today?"


def _speak_greeting(delay: float = 2.0):
    """
    Speak a time-aware greeting in a background thread so it never blocks.
    `delay` lets startup wait for the SAPI engine; on-demand calls use 0.
    """
    import threading, time

    def _greet():
        if delay:
            time.sleep(delay)  # Let the server fully start before speaking
        try:
            greeting = _build_greeting_text()
            log.info(f"Greeting: {greeting}")
            from controllers.voice_output_controller import speak_nonblocking
            speak_nonblocking(greeting)
        except Exception as e:
            log.warning(f"Greeting failed (non-fatal): {e}")

    threading.Thread(target=_greet, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("DesktopPilot agent starting up")
    init_db()
    log.info("SQLite initialized")
    index_files()
    log.info("File index built")
    auto_register_projects()
    log.info("Project auto-discovery complete")
    start_file_watcher()
    log.info("File watcher started")
    # Start clipboard monitor
    from controllers.clipboard_manager_controller import start_clipboard_monitor
    start_clipboard_monitor()
    log.info("Clipboard monitor started")
    # Pre-warm Bedrock connection in background (reduces first-call latency)
    from voice.pipeline import schedule_prewarm
    schedule_prewarm()
    log.info("Bedrock pre-warm scheduled")
    # Greet user on startup
    _speak_greeting()
    log.info("Startup greeting queued")
    yield
    stop_file_watcher()
    log.info("DesktopPilot agent shut down")


app = FastAPI(title="DesktopPilot AI", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(data):
    return {"status": "ok", "data": data, "error": None}

def err(message: str, code: int = 400):
    raise HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "DesktopPilot AI v2.0.0"}


# ── Greeting ──────────────────────────────────────────────────────────────────

class GreetRequest(BaseModel):
    speak: bool = True

@app.post("/greet")
async def greet(req: GreetRequest = GreetRequest()):
    """
    Speak a fresh time-aware greeting on demand.
    Called by the frontend whenever the app/page opens or reloads,
    since the backend keeps running and the startup greeting only fires once.
    """
    text = _build_greeting_text()
    if req.speak:
        _speak_greeting(delay=0)  # speak immediately, non-blocking
    return ok({"greeting": text})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        log.info(f"Received audio: {len(audio_bytes)} bytes")
        text = await transcribe_audio_bytes(audio_bytes)
        log.info(f"Transcript: {text}")
        return ok({"text": text})
    except Exception as e:
        log.error(f"Transcription error: {e}")
        err(str(e))


# ── Plan ──────────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    text: str
    user_id: str = "default"

@app.post("/plan")
async def plan(req: PlanRequest):
    if not req.text.strip():
        err("Command text cannot be empty")

    # Check credits first
    from ai.memory import deduct_credits
    try:
        remaining = deduct_credits(req.user_id, amount=1)
    except ValueError as e:
        err(str(e), 402)
        return

    try:
        log.info(f"Planning (parallel pipeline): {req.text}")

        # ── Parallel pipeline: cache check + ack + Bedrock + prewarm ──
        from voice.pipeline import run_parallel_pipeline, prewarm_bedrock

        # Pre-warm while we also kick off the pipeline
        # (prewarm is a no-op if already warmed)
        plan_data = await run_parallel_pipeline(
            text=req.text,
            user_id=req.user_id,
            ws_broadcast=ws_manager.broadcast,
        )

        log.info(f"Plan: {len(plan_data.get('tasks', []))} tasks")

        await ws_manager.broadcast({
            "type": "plan_ready",
            "plan": plan_data,
            "credits_remaining": remaining if remaining != -1 else None,
        })

        return ok({"plan": plan_data, "credits_remaining": remaining})
    except Exception as e:
        log.error(f"Planning error: {e}")
        from controllers.voice_output_controller import speak
        speak("Sorry, I couldn't understand that command.")
        err(str(e))


# ── Pipeline Stats (cache hit rate, latency info) ─────────────────────────────

@app.get("/pipeline/stats")
async def pipeline_stats():
    from voice.pipeline import command_cache
    return ok({"cache": command_cache.stats()})


# ── Execute ───────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    plan: dict
    user_id: str = "default"

@app.post("/execute")
async def execute(req: ExecuteRequest):
    try:
        tasks = req.plan.get("tasks", [])
        log.info(f"Executing {len(tasks)} tasks")

        await ws_manager.broadcast({"type": "execution_start", "total": len(tasks)})

        from database.sqlite_manager import save_command
        from ai.memory import save_command_cloud
        from controllers.notification_controller import notify_done

        intent = req.plan.get("intent", "")
        if intent:
            save_command(intent)

        results = []
        start = time.time()
        prev_tool = ""

        for i, task in enumerate(tasks):
            tool = task.get("tool", "")
            message = ""
            success = False

            # ── Execute with retry ──────────────────────────────────────────
            for attempt in range(2):  # Try up to 2 times
                try:
                    message = await execute_task(task, req.user_id, prev_tool=prev_tool)
                    success = True
                    break  # Success — stop retrying
                except Exception as e:
                    err_msg = str(e)
                    if attempt == 0:
                        log.warning(f"Task '{tool}' failed (attempt 1): {err_msg} — retrying in 1s")
                        await ws_manager.broadcast({
                            "type": "step_retry",
                            "index": i,
                            "tool": tool,
                            "message": f"Retrying: {err_msg[:60]}",
                        })
                        await asyncio.sleep(1.0)
                    else:
                        message = f"Task '{tool}' failed: {err_msg}"
                        log.error(f"Task '{tool}' failed after retry: {err_msg}")

            # ── Check if failure is critical (blocks remaining steps) ──────
            if not success:
                critical_tools = {"open_application", "open_project", "create_project",
                                  "run_terminal", "browser_goto", "open_browser"}
                is_critical = tool in critical_tools and i < len(tasks) - 1

                # Try AI-suggested alternative if critical
                if is_critical:
                    alternative = _get_error_alternative(tool, task, message)
                    if alternative:
                        log.info(f"Trying alternative for '{tool}': {alternative}")
                        try:
                            message = await execute_task(alternative, req.user_id, prev_tool=prev_tool)
                            success = True
                            message = f"[Alternative] {message}"
                        except Exception as e2:
                            message = f"Task '{tool}' failed (alternative also failed): {e2}"

            result = {"tool": tool, "success": success, "message": message}
            results.append(result)
            prev_tool = tool

            await ws_manager.broadcast({
                "type": "step_update",
                "index": i,
                "tool": tool,
                "success": success,
                "message": message,
            })

            # ── Stop execution if critical step failed ─────────────────────
            if not success and tool in {"open_project", "create_project"}:
                # Skip remaining steps that depend on this one
                for j in range(i + 1, len(tasks)):
                    skipped_tool = tasks[j].get("tool", "")
                    skip_result = {
                        "tool": skipped_tool,
                        "success": False,
                        "message": f"Skipped — previous step '{tool}' failed",
                    }
                    results.append(skip_result)
                    await ws_manager.broadcast({
                        "type": "step_update",
                        "index": j,
                        "tool": skipped_tool,
                        "success": False,
                        "message": skip_result["message"],
                    })
                break  # Stop the loop

        duration_ms = int((time.time() - start) * 1000)
        success_count = sum(1 for r in results if r["success"])

        save_command_cloud(
            user_id=req.user_id,
            command=intent,
            intent=intent,
            status="completed" if success_count == len(results) else "partial",
            duration_ms=duration_ms,
        )

        await ws_manager.broadcast({
            "type": "execution_done",
            "success": success_count,
            "total": len(results),
        })

        notify_done(success_count, len(results))

        # Speak result — natural, human-like responses (NON-BLOCKING)
        # We capture the spoken text + estimate duration so the frontend
        # can animate the waveform for exactly as long as speech plays.
        spoken_text = ""
        plan_has_speak = any(t.get("tool") == "speak" for t in tasks)
        if not plan_has_speak:
            from controllers.voice_output_controller import speak_nonblocking
            if success_count == len(results) and results:
                spoken_text = _generate_voice_response(results, intent)
            elif success_count < len(results):
                failed = [r for r in results if not r["success"]]
                skipped = [r for r in results if "Skipped" in r.get("message", "")]
                if failed and not skipped:
                    fail_tool = failed[0]["tool"].replace("_", " ")
                    spoken_text = f"I completed {success_count} of {len(results)} steps, Sir. The {fail_tool} step ran into an issue. You may want to try again."
                elif skipped:
                    spoken_text = f"I stopped at step {success_count + 1} of {len(results)}, Sir — the remaining steps were skipped because a required step failed."
                else:
                    spoken_text = "I completed some steps but a few didn't work. Please check."

            if spoken_text:
                speak_nonblocking(spoken_text)

        # Estimate speech duration (ms) so frontend animates the waveform
        # for the full speech length. ~165 wpm ≈ 2.75 words/sec.
        word_count = len(spoken_text.split()) if spoken_text else 0
        speech_ms = int(word_count / 2.75 * 1000) + 600 if word_count else 0

        return ok({
            "results": results,
            "spoken_text": spoken_text,
            "speech_ms": speech_ms,
        })
    except Exception as e:
        log.error(f"Execution error: {e}")
        err(str(e))


# ── Credits ───────────────────────────────────────────────────────────────────

@app.get("/credits")
async def get_credits_route(user_id: str = "default"):
    from ai.memory import get_credits
    try:
        return ok({"credits_remaining": get_credits(user_id), "user_id": user_id})
    except Exception as e:
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
async def get_commands(user_id: str = "default"):
    from database.sqlite_manager import get_recent_commands
    try:
        return ok({"commands": get_recent_commands(limit=20)})
    except Exception as e:
        err(str(e))


# ── Files ─────────────────────────────────────────────────────────────────────

@app.get("/files/search")
async def search_files(q: str = ""):
    from database.sqlite_manager import search_file
    try:
        return ok({"files": search_file(q)})
    except Exception as e:
        err(str(e))

@app.post("/files/reindex")
async def reindex_files():
    try:
        count = index_files()
        return ok({"indexed": count})
    except Exception as e:
        err(str(e))

class OpenFileRequest(BaseModel):
    path: str

@app.post("/files/open")
async def open_file_endpoint(req: OpenFileRequest):
    try:
        os.startfile(req.path)
        return ok({"message": f"Opened: {req.path}"})
    except Exception as e:
        err(str(e))


# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/projects")
async def list_projects_route():
    from database.sqlite_manager import list_projects
    try:
        return ok({"projects": list_projects()})
    except Exception as e:
        err(str(e))

class ProjectRequest(BaseModel):
    name: str
    path: str
    framework: str = ""
    start_command: str = ""

@app.post("/projects")
async def create_project_route(req: ProjectRequest):
    from database.sqlite_manager import register_project
    try:
        register_project(req.name, req.path, req.framework, req.start_command)
        return ok({"message": f"Project '{req.name}' registered"})
    except Exception as e:
        err(str(e))


# ── Screen Reading ────────────────────────────────────────────────────────────

@app.get("/screen/read")
async def read_screen_route(mode: str = "full"):
    """Capture screen and extract text via Amazon Textract."""
    from controllers.screen_reader_controller import read_screen
    try:
        text = read_screen(mode)
        return ok({"text": text, "mode": mode})
    except Exception as e:
        err(str(e))

@app.get("/screen/analyze")
async def analyze_screen_route():
    """Full screen analysis — text, forms, tables."""
    from controllers.screen_reader_controller import analyze_screen
    try:
        result = analyze_screen()
        return ok(result)
    except Exception as e:
        err(str(e))


# ── User Profile ──────────────────────────────────────────────────────────────

@app.get("/profile")
async def get_profile_route():
    from controllers.form_filler_controller import get_profile
    try:
        return ok({"profile": get_profile()})
    except Exception as e:
        err(str(e))

class ProfileUpdateRequest(BaseModel):
    field: str
    value: str

@app.post("/profile")
async def update_profile_route(req: ProfileUpdateRequest):
    from controllers.form_filler_controller import update_profile
    try:
        result = update_profile(req.field, req.value)
        return ok({"message": result})
    except Exception as e:
        err(str(e))

class ProfileBulkRequest(BaseModel):
    profile: dict

@app.put("/profile")
async def set_full_profile(req: ProfileBulkRequest):
    from controllers.form_filler_controller import save_profile
    try:
        result = save_profile(req.profile)
        return ok({"message": result})
    except Exception as e:
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
    else:
        err(result["error"], 400)

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/login")
async def auth_login(req: LoginRequest):
    from controllers.auth_controller import login
    result = login(req.email, req.password)
    if result["success"]:
        return ok(result)
    else:
        err(result["error"], 401)


# ──────────────────────────────────────────────────────────────────────────────
# FEATURE 1 — AI MEETING ASSISTANT
# ──────────────────────────────────────────────────────────────────────────────

class MeetingStartRequest(BaseModel):
    title: str = ""

@app.post("/meeting/start")
async def meeting_start(req: MeetingStartRequest):
    from controllers.meeting_controller import start_meeting
    try:
        result = start_meeting(req.title)
        return ok({"message": result})
    except Exception as e:
        err(str(e))

@app.post("/meeting/stop")
async def meeting_stop():
    from controllers.meeting_controller import stop_meeting
    try:
        result = stop_meeting()
        if "error" in result:
            err(result["error"])
        return ok(result)
    except Exception as e:
        err(str(e))

class MeetingProcessRequest(BaseModel):
    wav_path:      str
    title:         str
    send_email_to: str = ""

@app.post("/meeting/process")
async def meeting_process(req: MeetingProcessRequest):
    from controllers.meeting_controller import process_meeting
    try:
        result = await process_meeting(req.wav_path, req.title, req.send_email_to)
        await ws_manager.broadcast({"type": "meeting_processed", "result": result})
        return ok(result)
    except Exception as e:
        err(str(e))

@app.get("/meeting/status")
async def meeting_status():
    from controllers.meeting_controller import get_meeting_status
    try:
        return ok(get_meeting_status())
    except Exception as e:
        err(str(e))


# ──────────────────────────────────────────────────────────────────────────────
# FEATURE 5 — AI CLIPBOARD MANAGER
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/clipboard/history")
async def clipboard_history(limit: int = 30):
    from controllers.clipboard_manager_controller import get_clipboard_history_smart
    try:
        return ok({"entries": get_clipboard_history_smart(limit)})
    except Exception as e:
        err(str(e))

@app.get("/clipboard/status")
async def clipboard_status():
    from controllers.clipboard_manager_controller import get_monitor_status
    try:
        return ok(get_monitor_status())
    except Exception as e:
        err(str(e))

class ClipboardQueryRequest(BaseModel):
    query: str

@app.post("/clipboard/query")
async def clipboard_query(req: ClipboardQueryRequest):
    from controllers.clipboard_manager_controller import ai_clipboard_query
    try:
        result = ai_clipboard_query(req.query)
        return ok({"answer": result})
    except Exception as e:
        err(str(e))

class ClipboardFilterRequest(BaseModel):
    tag: str  # code | email | url | phone | address | text

@app.post("/clipboard/filter")
async def clipboard_filter(req: ClipboardFilterRequest):
    from controllers.clipboard_manager_controller import find_clip_by_type
    try:
        return ok({"entries": find_clip_by_type(req.tag)})
    except Exception as e:
        err(str(e))

class ClipboardPasteRequest(BaseModel):
    entry_id: int

@app.post("/clipboard/paste")
async def clipboard_paste(req: ClipboardPasteRequest):
    from controllers.clipboard_manager_controller import paste_clip
    try:
        result = paste_clip(req.entry_id)
        return ok({"message": result})
    except Exception as e:
        err(str(e))

@app.delete("/clipboard/history")
async def clipboard_clear():
    from controllers.clipboard_manager_controller import clear_clipboard_history
    try:
        return ok({"message": clear_clipboard_history()})
    except Exception as e:
        err(str(e))


# ──────────────────────────────────────────────────────────────────────────────
# FEATURE 6 — FOCUS MODE / POMODORO
# ──────────────────────────────────────────────────────────────────────────────

class FocusStartRequest(BaseModel):
    duration_hours: float = 2.0
    goal:           str   = ""
    focus_min:      int   = 25
    break_min:      int   = 5

@app.post("/focus/start")
async def focus_start(req: FocusStartRequest):
    from controllers.focus_controller import start_focus_mode
    try:
        result = start_focus_mode(
            req.duration_hours, req.goal, req.focus_min, req.break_min
        )
        return ok({"message": result})
    except Exception as e:
        err(str(e))

@app.post("/focus/stop")
async def focus_stop():
    from controllers.focus_controller import stop_focus_mode
    try:
        result = stop_focus_mode()
        if "error" in result:
            err(result["error"])
        await ws_manager.broadcast({"type": "focus_ended", "report": result})
        return ok(result)
    except Exception as e:
        err(str(e))

@app.get("/focus/status")
async def focus_status_route():
    from controllers.focus_controller import get_focus_status
    try:
        return ok(get_focus_status())
    except Exception as e:
        err(str(e))

@app.get("/focus/sessions")
async def focus_sessions():
    from controllers.focus_controller import get_focus_sessions
    try:
        return ok({"sessions": get_focus_sessions()})
    except Exception as e:
        err(str(e))


# ── Buy Credits ───────────────────────────────────────────────────────────────

class BuyCreditsRequest(BaseModel):
    user_id: str
    plan: str  # "starter", "pro", "team"

@app.post("/credits/buy")
async def buy_credits(req: BuyCreditsRequest):
    """Add credits to user account based on plan purchased."""
    PLANS = {
        "starter": 500,
        "pro":     2000,
        "team":    10000,
    }

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
        log.info(f"Credits purchased: {req.plan} (+{amount}) → balance: {new_balance}")

        return ok({
            "plan": req.plan,
            "credits_added": amount,
            "credits_remaining": new_balance,
        })
    except Exception as e:
        log.error(f"Buy credits failed: {e}")
        err(str(e))


# ── Voice Response Generator ──────────────────────────────────────────────────

def _get_error_alternative(tool: str, task: dict, error: str) -> dict | None:
    """
    Suggest an alternative task when a step fails.
    Returns an alternative task dict, or None if no alternative exists.
    """
    error_lower = error.lower()

    # App failed to open → try Windows Search
    if tool == "open_application":
        app_name = task.get("name", "")
        if "not found" in error_lower or "failed" in error_lower:
            return {"tool": "search_web", "query": f"open {app_name} download"}

    # Browser navigation failed → try subprocess open
    if tool == "browser_goto":
        url = task.get("url", "")
        if url:
            return {"tool": "open_browser", "url": url}

    # Project not found in registry → try opening Desktop
    if tool == "open_project":
        project = task.get("project", "")
        if "not found" in error_lower:
            return {"tool": "open_file", "name": project}

    # Terminal command failed → open terminal without command
    if tool == "run_terminal":
        cmd = task.get("command", "")
        if "blocked" in error_lower:
            return None  # Safety block — don't retry
        return {"tool": "open_application", "name": "Terminal"}

    return None


def _generate_voice_response(results: list, intent: str) -> str:
    """Generate natural, human-like voice response based on what was executed."""
    if not results:
        return "Done, Sir."

    first = results[0]
    tool = first.get("tool", "")
    msg = first.get("message", "")

    # Single-step responses
    if len(results) == 1:
        if tool == "open_application":
            app_name = msg.replace("Opened ", "").replace(" via Windows Search", "")
            return f"{app_name} is now open for you, Sir."

        elif tool == "open_browser":
            return "I've opened that in your browser, Sir."

        elif tool == "open_setting":
            return "Settings panel is open, Sir."

        elif tool == "open_project":
            return "Your project is open in VS Code, Sir."

        elif tool == "open_file":
            return "I've opened that file for you, Sir."

        elif tool == "take_screenshot":
            return "Screenshot taken and saved to your desktop, Sir."

        elif tool == "system_info":
            # Speak the actual info
            short = msg[:100] if len(msg) < 100 else msg.split('\n')[0]
            return short

        elif tool == "generate_code":
            return "Your code has been generated and executed. Check VS Code for the file, Sir."

        elif tool == "create_file":
            return "File created and opened for you, Sir."

        elif tool == "create_project":
            return "Project scaffolded and opened in VS Code, Sir."

        elif tool == "compose_email":
            return "Gmail compose is open with your email filled in, Sir."

        elif tool == "send_whatsapp":
            return "WhatsApp message sent, Sir."

        elif tool == "smart_reply":
            return "I've typed a reply for you, Sir."

        elif tool == "brightness_up" or tool == "brightness_down":
            return "Brightness adjusted, Sir."

        elif tool == "volume_up" or tool == "volume_down":
            return "Volume adjusted, Sir."

        elif tool == "mute":
            return "Mute toggled, Sir."

        elif tool == "kill_process":
            return f"Done. {msg}"

        elif tool == "snap_window":
            return "Window snapped, Sir."

        elif tool == "minimize_all":
            return "All windows minimized, Sir."

        elif tool == "start_timer":
            return msg

        elif tool == "copy_screen":
            return "Screen text copied to your clipboard, Sir."

        elif tool == "fill_form":
            return "Form filled with your details, Sir."

        elif tool == "run_terminal":
            return "Command is running in the terminal, Sir."

        # ── File Operations ──
        elif tool == "copy_file":
            return f"File copied. {msg}"

        elif tool == "copy_files_by_type":
            return msg

        elif tool == "move_file":
            return f"File moved. {msg}"

        elif tool == "move_files_by_type":
            return msg

        elif tool == "rename_file":
            return f"File renamed. {msg}"

        elif tool == "delete_file":
            return f"File deleted, Sir."

        elif tool == "delete_by_pattern":
            return msg

        elif tool == "create_folder":
            return f"Folder created, Sir."

        elif tool == "zip_folder":
            return "Zipped successfully, Sir."

        elif tool == "unzip_file":
            return "Extracted successfully, Sir."

        elif tool == "cleanup_desktop":
            return "Desktop organized into folders, Sir."

        # ── Info tools — speak the result ──
        elif tool in ("list_large_files", "find_duplicates", "check_ports",
                      "show_env_variables", "get_disk_usage", "get_wifi_info",
                      "show_installed_programs", "get_startup_programs",
                      "check_network_speed"):
            # Speak a short summary of the result
            lines = msg.split('\n')
            if len(lines) > 3:
                return f"Here's what I found, Sir. {lines[0]}. Check the app for full details."
            return msg[:150] if msg else "Done, Sir."

        # ── System Maintenance ──
        elif tool == "clear_recycle_bin":
            return "Recycle bin emptied, Sir."

        elif tool == "flush_dns":
            return "DNS cache flushed, Sir."

        elif tool == "open_disk_cleanup":
            return "Disk cleanup is open, Sir."

        elif tool == "open_device_manager":
            return "Device manager is open, Sir."

        elif tool == "open_services":
            return "Services manager is open, Sir."

        elif tool == "check_updates":
            return "Windows Update is open, Sir."

        elif tool == "shutdown":
            return msg

        elif tool == "restart":
            return msg

        elif tool == "cancel_shutdown":
            return "Shutdown cancelled, Sir."

        else:
            return "Done, Sir."

    # Multi-step responses
    else:
        tools_used = set(r["tool"] for r in results)

        if "open_application" in tools_used and "type_text" in tools_used:
            return "I've opened the app and typed everything for you, Sir."

        elif "open_project" in tools_used and "run_terminal" in tools_used:
            return "Your project is open and the server is starting, Sir."

        elif "create_file" in tools_used:
            return "File created with all the content, Sir."

        elif "compose_email" in tools_used:
            return "Your email is composed and ready to send, Sir."

        else:
            return f"All {len(results)} steps completed, Sir."
