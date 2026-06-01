# DesktopPilot AI — Phase 2: Intelligence & Real-Time Features

> **Prerequisite:** Phase 1 complete and verified — Electron app running, FastAPI backend healthy, voice → plan → execute working for basic commands.
>
> **Goal:** Upgrade from a working prototype to a smart, real-time agent. Add Playwright browser control, live file watching, DynamoDB memory sync, credits system, WebSocket streaming, project auto-discovery, and Windows notifications.

---

## Phase 2 Scope

| Area | What Gets Built | Why |
|---|---|---|
| Playwright Browser Control | Full browser automation replacing `subprocess start` | Enables form filling, Gmail compose, web scraping |
| Watchdog File Watcher | Re-index files on change, not just startup | Files panel stays current without manual refresh |
| DynamoDB Memory Sync | Cloud memory replacing SQLite-only storage | Memory persists across reinstalls, syncs to web dashboard |
| Credits System | Deduct credits per Bedrock call, enforce limit | Monetization foundation for Phase 3 billing |
| WebSocket Streaming | Stream execution steps to web dashboard in real time | Web dashboard shows live execution without polling |
| Project Auto-Discovery | Scan for `package.json`, `manage.py`, `requirements.txt` | Auto-populate project registry on first run |
| Windows Notifications | Toast notifications on command completion | User knows when background tasks finish |
| Playwright Gmail | Full Gmail compose with AI-generated body | Impressive hackathon demo |

---

## New Dependencies

```bash
# Backend
pip install playwright==1.44.0 watchdog==4.0.1 websockets==12.0

# Install Playwright browsers (run once)
playwright install chromium
```

```bash
# Electron app
npm install ws@8.17.1
```

---

## Step 1 — Playwright Browser Controller

Replace the simple `subprocess start` browser controller with full Playwright automation.

`backend/controllers/browser_controller.py` — **replace entirely:**

```python
"""
Browser Controller — Playwright-based web automation.
Uses async Playwright for non-blocking execution.
"""
import asyncio
import logging
import subprocess
import urllib.parse

log = logging.getLogger(__name__)

# Try Playwright; fall back to subprocess if not installed
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    log.warning("Playwright not installed — using subprocess fallback")


async def open_url(url: str) -> str:
    """Open a URL. Uses Playwright if available, else default browser."""
    if PLAYWRIGHT_AVAILABLE:
        return await _playwright_open(url)
    return _subprocess_open(url)


async def _playwright_open(url: str) -> str:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=["--start-maximized"]
            )
            context = await browser.new_context(no_viewport=True)
            page    = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            log.info(f"Playwright opened: {url}")
            # Don't close — leave browser open for user
            return f"Opened browser: {url}"
    except Exception as e:
        log.warning(f"Playwright failed ({e}), falling back to subprocess")
        return _subprocess_open(url)


def _subprocess_open(url: str) -> str:
    subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
    return f"Opened browser: {url}"


async def search_web(query: str) -> str:
    encoded = urllib.parse.quote_plus(query)
    return await open_url(f"https://www.google.com/search?q={encoded}")


async def open_gmail_compose(to: str = "", subject: str = "", body: str = "") -> str:
    """Open Gmail compose with pre-filled fields using Playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        params = urllib.parse.urlencode({"view": "cm", "to": to, "su": subject, "body": body})
        return _subprocess_open(f"https://mail.google.com/mail/?{params}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, channel="chrome")
            context = await browser.new_context()
            page    = await context.new_page()

            # Open Gmail
            await page.goto("https://mail.google.com", wait_until="networkidle", timeout=20000)

            # Click Compose button
            compose_btn = page.locator('[gh="cm"]')
            await compose_btn.wait_for(timeout=10000)
            await compose_btn.click()

            # Fill recipient
            if to:
                to_field = page.locator('[name="to"]')
                await to_field.wait_for(timeout=5000)
                await to_field.fill(to)

            # Fill subject
            if subject:
                subj_field = page.locator('[name="subjectbox"]')
                await subj_field.fill(subject)

            # Fill body
            if body:
                body_field = page.locator('[aria-label="Message Body"]')
                await body_field.fill(body)

            log.info(f"Gmail compose opened for: {to}")
            return f"Gmail compose opened — to: {to}, subject: {subject}"

    except Exception as e:
        log.error(f"Gmail automation failed: {e}")
        # Fallback to URL compose
        params = urllib.parse.urlencode({"view": "cm", "to": to, "su": subject, "body": body})
        return _subprocess_open(f"https://mail.google.com/mail/?{params}")
```

Update `automation/executor.py` to `await` the async browser calls:

```python
elif tool == "open_browser":
    url = task.get("url", "https://google.com")
    return await browser_controller.open_url(url)

elif tool == "search_web":
    return await browser_controller.search_web(task.get("query", ""))

elif tool == "compose_email":
    return await browser_controller.open_gmail_compose(
        task.get("to", ""), task.get("subject", ""), task.get("body", "")
    )
```

---

## Step 2 — Watchdog File Watcher

Add background file watching so the index stays current without restarting.

`backend/indexer/file_indexer.py` — **add to bottom:**

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

_observer = None
_reindex_lock = threading.Lock()


class _ChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            _handle_change(event.src_path, "created")

    def on_deleted(self, event):
        if not event.is_directory:
            _handle_change(event.src_path, "deleted")

    def on_moved(self, event):
        if not event.is_directory:
            _handle_change(event.dest_path, "moved")


def _handle_change(path: str, event_type: str):
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return
    # Debounce: only re-index if lock is free
    if _reindex_lock.acquire(blocking=False):
        try:
            log.info(f"File {event_type}: {path} — re-indexing")
            index_files()
        finally:
            _reindex_lock.release()


def start_file_watcher():
    """Start background watchdog observer. Call once after index_files()."""
    global _observer
    if _observer and _observer.is_alive():
        return

    _observer = Observer()
    handler = _ChangeHandler()

    for directory in SCAN_DIRS:
        if os.path.exists(directory):
            _observer.schedule(handler, directory, recursive=True)

    _observer.daemon = True
    _observer.start()
    log.info("File watcher started")
    return _observer


def stop_file_watcher():
    global _observer
    if _observer:
        _observer.stop()
        _observer.join()
        _observer = None
```

Update `backend/main.py` lifespan to start the watcher:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    index_files()
    start_file_watcher()          # ← add this
    log.info("File watcher started")
    yield
    stop_file_watcher()           # ← add this
    log.info("DesktopPilot shutting down")
```

---

## Step 3 — DynamoDB Memory Sync

Wire the memory layer to DynamoDB so context persists across sessions and syncs to the web dashboard.

`backend/ai/memory.py` — **replace entirely:**

```python
"""
Memory layer — reads/writes DynamoDB for cloud sync,
falls back to SQLite when AWS is unavailable.
"""
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from database.sqlite_manager import get_last_project, get_recent_commands

log = logging.getLogger(__name__)

REGION    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
TABLE     = os.getenv("DYNAMODB_TABLE_MEMORY", "DesktopPilotMemory")
CMD_TABLE = os.getenv("DYNAMODB_TABLE_COMMANDS", "DesktopPilotCommands")

_dynamo = None

def _get_dynamo():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.resource("dynamodb", region_name=REGION)
    return _dynamo


def get_context(user_id: str = "default") -> dict:
    """Return memory context — tries DynamoDB first, falls back to SQLite."""
    # Always get local data
    last_project    = get_last_project()
    recent_commands = [c["command"] for c in get_recent_commands(limit=5)]

    # Try to enrich from DynamoDB
    try:
        table    = _get_dynamo().Table(TABLE)
        response = table.get_item(Key={"user_id": user_id})
        item     = response.get("Item", {})

        if item.get("last_project"):
            last_project = item["last_project"]

        return {
            "last_project":     last_project,
            "recent_commands":  recent_commands,
            "credits_remaining": item.get("credits_remaining", 100),
            "source":           "dynamodb",
        }
    except (ClientError, NoCredentialsError) as e:
        log.warning(f"DynamoDB unavailable, using local memory: {e}")
        return {
            "last_project":     last_project,
            "recent_commands":  recent_commands,
            "credits_remaining": 100,
            "source":           "local",
        }


def save_command_to_dynamo(user_id: str, command: str, intent: str,
                            plan: dict, status: str, duration_ms: int,
                            credits_used: int = 1):
    """Save a completed command to DynamoDB command history."""
    try:
        table = _get_dynamo().Table(CMD_TABLE)
        table.put_item(Item={
            "user_id":     user_id,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "command":     command,
            "intent":      intent,
            "plan":        plan,
            "status":      status,
            "duration_ms": duration_ms,
            "credits_used": credits_used,
        })
        log.info(f"Command saved to DynamoDB: {command[:50]}")
    except (ClientError, NoCredentialsError) as e:
        log.warning(f"Could not save to DynamoDB: {e}")


def update_last_project(user_id: str, project: dict):
    """Update last used project in DynamoDB."""
    try:
        table = _get_dynamo().Table(TABLE)
        table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET last_project = :p, last_updated = :t",
            ExpressionAttributeValues={
                ":p": project,
                ":t": datetime.now(timezone.utc).isoformat(),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        log.warning(f"Could not update DynamoDB: {e}")


def deduct_credits(user_id: str, amount: int = 1) -> int:
    """Deduct credits and return remaining balance. Returns -1 if DynamoDB unavailable."""
    try:
        table    = _get_dynamo().Table(TABLE)
        response = table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET credits_remaining = credits_remaining - :n",
            ConditionExpression="credits_remaining >= :n",
            ExpressionAttributeValues={":n": amount},
            ReturnValues="UPDATED_NEW",
        )
        return int(response["Attributes"]["credits_remaining"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError("Insufficient credits")
        log.warning(f"DynamoDB credits error: {e}")
        return -1
    except NoCredentialsError:
        return -1


def enrich_prompt(user_command: str, user_id: str = "default") -> str:
    """Inject memory context into the Bedrock prompt."""
    context = get_context(user_id)
    lines   = []

    if context["last_project"]:
        p = context["last_project"]
        lines.append(f"User's last project: {p.get('name')} at {p.get('path')}")

    if context["recent_commands"]:
        lines.append(f"Recent commands: {', '.join(context['recent_commands'])}")

    memory_block = "\n".join(lines)
    if memory_block:
        return f"Context:\n{memory_block}\n\nCommand: {user_command}"
    return f"Command: {user_command}"
```

---

## Step 4 — Credits System

Add credits enforcement to the `/plan` route in `backend/main.py`:

```python
@app.post("/plan")
async def plan(req: PlanRequest):
    if not req.text.strip():
        err("Command text cannot be empty")
    try:
        # Check credits before calling Bedrock
        from ai.memory import deduct_credits
        remaining = deduct_credits("default", amount=1)
        if remaining == 0:
            err("No credits remaining. Please purchase more credits at desktoppilot.vercel.app/dashboard", 402)

        log.info(f"Planning command: {req.text}")
        plan_data = await generate_plan(req.text)
        log.info(f"Plan generated: {len(plan_data.get('tasks', []))} tasks")
        return ok({"plan": plan_data, "credits_remaining": remaining})
    except ValueError as e:
        err(str(e), 402)
    except Exception as e:
        log.error(f"Planning error: {e}")
        err(str(e))
```

---

## Step 5 — WebSocket Streaming

Add a WebSocket endpoint to `backend/main.py` so the web dashboard can receive live execution updates.

```python
from fastapi import WebSocket, WebSocketDisconnect
import asyncio

# Connection manager
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        for ws in self.active[:]:
            try:
                await ws.send_json(data)
            except Exception:
                self.active.remove(ws)

ws_manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

Update `executor.py` to broadcast step updates:

```python
# In execute_plan(), after each task completes:
from main import ws_manager   # import at top of file

# After each task result:
await ws_manager.broadcast({
    "type":    "step_update",
    "index":   i,
    "tool":    tool,
    "success": result_ok,
    "message": result_msg,
})
```

Update `web/src/lib/websocket.js` to connect to `ws://localhost:8000/ws` instead of `:8765`.

---

## Step 6 — Project Auto-Discovery

Add auto-discovery to `backend/indexer/file_indexer.py`:

```python
import json

PROJECT_MARKERS = {
    "package.json":    ("Node.js/React", "npm start"),
    "manage.py":       ("Django",        "python manage.py runserver"),
    "requirements.txt":("Python",        "python main.py"),
    "Cargo.toml":      ("Rust",          "cargo run"),
    "pom.xml":         ("Java/Maven",    "mvn spring-boot:run"),
    "go.mod":          ("Go",            "go run ."),
}

def discover_projects(base_dirs: list[str] = None) -> list[dict]:
    """Scan directories for project markers and return project metadata."""
    if base_dirs is None:
        base_dirs = ["D:/Projects", "C:/Projects",
                     os.path.expanduser("~/Projects"),
                     os.path.expanduser("~/Documents")]

    discovered = []
    for base in base_dirs:
        if not os.path.exists(base):
            continue
        for entry in os.scandir(base):
            if not entry.is_dir():
                continue
            for marker, (framework, start_cmd) in PROJECT_MARKERS.items():
                marker_path = os.path.join(entry.path, marker)
                if os.path.exists(marker_path):
                    # Try to get project name from package.json
                    name = entry.name
                    if marker == "package.json":
                        try:
                            with open(marker_path) as f:
                                pkg = json.load(f)
                                name = pkg.get("name", entry.name)
                        except Exception:
                            pass

                    discovered.append({
                        "name":          name,
                        "path":          entry.path,
                        "framework":     framework,
                        "start_command": start_cmd,
                    })
                    break  # Only match first marker per directory

    return discovered
```

Call `discover_projects()` in the lifespan startup and register each to SQLite:

```python
# In main.py lifespan:
from indexer.file_indexer import discover_projects
from database.sqlite_manager import register_project

projects = discover_projects()
for p in projects:
    register_project(p["name"], p["path"], p["framework"], p["start_command"])
log.info(f"Auto-discovered {len(projects)} projects")
```

---

## Step 7 — Windows Toast Notifications

Add notifications when commands complete.

`backend/controllers/notification_controller.py`:

```python
"""
Windows toast notifications via win10toast or Windows Runtime.
"""
import logging
import subprocess

log = logging.getLogger(__name__)

def notify(title: str, message: str, duration: int = 5):
    """Show a Windows toast notification."""
    try:
        # Use PowerShell for reliable Windows 10/11 notifications
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02
        )
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("DesktopPilot AI")
        $notifier.Show($toast)
        """
        subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True, timeout=5
        )
        log.info(f"Notification sent: {title}")
    except Exception as e:
        log.warning(f"Notification failed: {e}")
```

Call `notify()` at the end of `executor.py` after all steps complete:

```python
from controllers.notification_controller import notify

# After all tasks complete:
success_count = sum(1 for r in results if r["success"])
notify(
    "DesktopPilot AI",
    f"Done — {success_count}/{len(results)} steps completed"
)
```

---

## Phase 2 Deliverables Checklist

### Browser Automation
- [ ] Playwright installed and `playwright install chromium` run
- [ ] `open_url` uses Playwright with subprocess fallback
- [ ] Gmail compose fills recipient, subject, body fields via Playwright
- [ ] `search_web` opens Google search in browser

### File Watcher
- [ ] Watchdog observer starts on backend startup
- [ ] File creation/deletion triggers re-index
- [ ] Files panel in Electron app reflects changes without manual refresh

### DynamoDB Memory
- [ ] `get_context()` reads from DynamoDB with SQLite fallback
- [ ] `save_command_to_dynamo()` called after each execution
- [ ] `update_last_project()` called when a project is opened
- [ ] Web dashboard `/dashboard` history tab shows real DynamoDB data

### Credits System
- [ ] `/plan` route deducts 1 credit per call
- [ ] 402 error returned when credits exhausted
- [ ] Credits remaining shown in Electron TitleBar
- [ ] Credits remaining returned in `/plan` response

### WebSocket Streaming
- [ ] `/ws` endpoint live in FastAPI
- [ ] Execution steps broadcast to connected clients
- [ ] Web dashboard connects to `ws://localhost:8000/ws`
- [ ] Web dashboard shows live step updates

### Project Auto-Discovery
- [ ] `discover_projects()` scans for 6 project marker files
- [ ] Discovered projects auto-registered in SQLite on startup
- [ ] Projects panel shows auto-discovered projects on first run

### Notifications
- [ ] Toast notification shown on command completion
- [ ] Notification shows success/failure count

---

## Next: Phase 3

Move to `README_PHASE3_AWS_PRODUCTION.md` to add:
- Lambda functions for cloud pipeline
- Step Functions orchestration
- DynamoDB table creation + IAM setup
- S3 audio pipeline
- CloudWatch logging
- electron-builder `.exe` production build
- Vercel production deployment with real download URL
