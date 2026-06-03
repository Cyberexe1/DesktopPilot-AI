"""
DesktopPilot AI — FastAPI Backend (Phase 2)
"""

import logging
import os
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

    # Check credits first (raises ValueError if insufficient)
    from ai.memory import deduct_credits
    try:
        remaining = deduct_credits(req.user_id, amount=1)
    except ValueError as e:
        err(str(e), 402)
        return

    try:
        log.info(f"Planning: {req.text}")
        plan_data = await generate_plan(req.text, user_id=req.user_id)
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
        speak(f"Sorry, I couldn't understand that command.")
        err(str(e))


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
            try:
                message = await execute_task(task, req.user_id, prev_tool=prev_tool)
                result = {"tool": tool, "success": True, "message": message}
            except Exception as e:
                result = {"tool": tool, "success": False, "message": f"Task '{tool}' failed: {e}"}

            results.append(result)
            prev_tool = tool  # Track for auto-wait logic

            await ws_manager.broadcast({
                "type": "step_update",
                "index": i,
                "tool": tool,
                "success": result["success"],
                "message": result["message"],
            })

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

        # Speak result — natural, human-like responses
        plan_has_speak = any(t.get("tool") == "speak" for t in tasks)
        if not plan_has_speak:
            from controllers.voice_output_controller import speak
            if success_count == len(results) and results:
                # Generate natural response based on what was done
                speech = _generate_voice_response(results, intent)
                speak(speech)
            elif success_count < len(results):
                failed = [r for r in results if not r["success"]]
                if failed:
                    speak(f"Sorry Sir, I ran into a problem. {failed[0]['message'][:60]}")
                else:
                    speak("I completed some steps but a few didn't work. Please check.")

        return ok({"results": results})
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


# ── Voice Response Generator ──────────────────────────────────────────────────

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
