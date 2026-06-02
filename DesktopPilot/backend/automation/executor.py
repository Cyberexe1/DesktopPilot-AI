"""
Task Executor — dispatches individual tasks to controllers.
Supports multi-step chaining with automatic waits between dependent steps.
"""

import asyncio
import json
import logging
import time

import requests

from controllers.app_controller import open_application
from controllers.browser_controller import open_url, search_web, open_gmail_compose
from controllers.file_controller import open_file
from controllers.file_writer_controller import create_file, write_to_file, create_project
from controllers.terminal_controller import run_in_terminal, open_vscode
from controllers.settings_controller import open_setting
from controllers.keyboard_controller import type_text, press_key
from controllers.screen_reader_controller import read_screen, read_screen_region, analyze_screen
from controllers.form_filler_controller import fill_form, get_profile, update_profile
from controllers.window_controller import (
    wait_for_window, is_correct_window_active,
    ensure_app_focused, get_active_window_title
)
from controllers.whatsapp_controller import send_whatsapp_message, open_whatsapp
from database.sqlite_manager import find_project
from ai.memory import update_last_project

log = logging.getLogger(__name__)

# Tools that need time for the app/page to load before the next step runs
TOOLS_NEEDING_WAIT_AFTER = {
    "open_application": 2.0,   # Wait 2s for app to open
    "open_browser":     3.0,   # Wait 3s for page to load
    "open_project":     2.5,   # Wait for VS Code to open
    "run_terminal":     1.5,   # Wait for terminal to appear
    "open_file":        1.5,   # Wait for file to open in app
    "open_setting":     1.0,   # Wait for settings to open
    "navigate":         3.0,   # Wait for page navigation
    "search_web":       3.0,   # Wait for search results
    "compose_email":    3.0,   # Wait for Gmail to load
    "create_file":      1.5,   # Wait for file to open
    "create_project":   2.0,   # Wait for VS Code
}

# Tools that interact with the active window (need the previous step to be ready)
TOOLS_NEEDING_FOCUS = {"type_text", "press_key", "click_element", "read_screen"}


async def execute_task(task: dict, user_id: str = "default", prev_tool: str = "") -> str:
    """
    Dispatch a single task to the correct controller.
    Automatically waits if the previous step needs time to complete.
    """
    tool = task.get("tool", "")
    loop = asyncio.get_event_loop()

    # Smart auto-wait: if this tool needs the previous step's app/page to be ready
    if prev_tool and tool in TOOLS_NEEDING_FOCUS:
        wait_time = TOOLS_NEEDING_WAIT_AFTER.get(prev_tool, 0)
        if wait_time > 0:
            log.info(f"Auto-waiting {wait_time}s for {prev_tool} to be ready...")
            await asyncio.sleep(wait_time)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    if tool == "open_application":
        name = task.get("name", "")
        result = await loop.run_in_executor(None, open_application, name)
        # Verify the app actually opened
        await loop.run_in_executor(None, wait_for_window, name, 5)
        return result

    elif tool == "open_project":
        project_name = task.get("project", "")
        project = find_project(project_name)
        if not project:
            return f"Project '{project_name}' not found in registry"
        result = await loop.run_in_executor(None, open_vscode, project["path"])
        await loop.run_in_executor(None, wait_for_window, "code", 5)
        update_last_project(user_id, project)
        return result

    elif tool == "open_file":
        return await loop.run_in_executor(None, open_file, task.get("name", ""))

    elif tool == "open_browser":
        url = task.get("url", "https://google.com")
        result = await open_url(url)
        # Wait for browser to appear
        await loop.run_in_executor(None, wait_for_window, "chrome", 5)
        return result

    elif tool == "navigate":
        url = task.get("url", "")
        result = await open_url(url)
        await asyncio.sleep(2)  # Wait for navigation
        return result

    elif tool == "search_web":
        return await search_web(task.get("query", ""))

    elif tool == "wait":
        # Explicit wait — user or AI requested a pause
        seconds = float(task.get("seconds", task.get("duration", 2)))
        seconds = min(seconds, 30)  # Cap at 30s for safety
        log.info(f"Waiting {seconds}s...")
        await asyncio.sleep(seconds)
        return f"Waited {seconds} seconds"

    elif tool == "wait_for_server":
        url = task.get("url", "http://localhost:8000")
        return await loop.run_in_executor(None, _wait_for_server, url)

    elif tool == "run_terminal":
        command = task.get("command", "")
        project_name = task.get("project", "")
        project = find_project(project_name) if project_name else None
        cwd = project["path"] if project else None
        return await loop.run_in_executor(None, run_in_terminal, command, cwd)

    elif tool == "open_setting":
        return await loop.run_in_executor(None, open_setting, task.get("name", ""))

    elif tool == "compose_email":
        result = await open_gmail_compose(
            task.get("to", ""),
            task.get("subject", ""),
            task.get("body", ""),
        )
        # Wait for browser/Gmail to open
        await loop.run_in_executor(None, wait_for_window, "mail", 5)
        return result

    elif tool == "type_text":
        text = task.get("text", "")
        # Safety check: verify something meaningful is in focus
        active_title = await loop.run_in_executor(None, get_active_window_title)
        if not active_title or active_title.lower() in ["", "desktop", "taskbar"]:
            return "Cannot type — no application window is in focus. Open an app first."
        log.info(f"Typing into: '{active_title}'")
        return await loop.run_in_executor(None, type_text, text)

    elif tool == "press_key":
        key = task.get("key", "")
        active_title = await loop.run_in_executor(None, get_active_window_title)
        if not active_title:
            return "Cannot press key — no window in focus"
        return await loop.run_in_executor(None, press_key, key)

    elif tool == "click_element":
        # Click at coordinates or use screen reading to find element
        x = int(task.get("x", 0))
        y = int(task.get("y", 0))
        from controllers.keyboard_controller import click_at
        return await loop.run_in_executor(None, click_at, x, y)

    elif tool == "create_file":
        filename  = task.get("filename", "")
        content   = task.get("content", "")
        directory = task.get("directory", "")
        return await loop.run_in_executor(None, create_file, filename, content, directory)

    elif tool == "write_to_file":
        filepath = task.get("filepath", "")
        content  = task.get("content", "")
        return await loop.run_in_executor(None, write_to_file, filepath, content)

    elif tool == "create_project":
        name      = task.get("name", task.get("project", ""))
        framework = task.get("framework", "html")
        directory = task.get("directory", "")
        return await loop.run_in_executor(None, create_project, name, framework, directory)

    elif tool == "read_screen":
        mode = task.get("mode", "full")
        return await loop.run_in_executor(None, read_screen, mode)

    elif tool == "analyze_screen":
        result = await loop.run_in_executor(None, analyze_screen)
        return f"Screen text ({result['line_count']} lines):\n{result['text'][:500]}"

    elif tool == "fill_form":
        return await loop.run_in_executor(None, fill_form)

    elif tool == "set_profile":
        field = task.get("field", "")
        value = task.get("value", "")
        return await loop.run_in_executor(None, update_profile, field, value)

    elif tool == "get_profile":
        profile = get_profile()
        filled = {k: v for k, v in profile.items() if v}
        return f"Profile: {json.dumps(filled, indent=2)}" if filled else "Profile is empty"

    elif tool == "send_whatsapp":
        contact = task.get("contact", task.get("to", ""))
        message = task.get("message", task.get("text", ""))
        return await send_whatsapp_message(contact, message)

    elif tool == "open_whatsapp":
        return await open_whatsapp()

    else:
        return f"Unknown tool: {tool}"


def _wait_for_server(url: str, timeout: int = 60, interval: int = 2) -> str:
    """Poll a URL until HTTP 200 or timeout."""
    log.info(f"Waiting for server at {url}")
    start = time.time()

    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                return f"Server ready at {url}"
        except requests.ConnectionError:
            pass
        time.sleep(interval)

    return f"Server at {url} did not respond within {timeout}s"
