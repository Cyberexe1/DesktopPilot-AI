"""
Task Executor — dispatches individual tasks to controllers.
Supports multi-step chaining with automatic waits between dependent steps.
"""

import asyncio
import json
import logging
import os
import time

import requests

from controllers.app_controller import open_application
from controllers.browser_controller import open_url, search_web, search_youtube, open_gmail_compose
from controllers.file_controller import open_file
from controllers.file_writer_controller import create_file, write_to_file, create_project
from controllers.terminal_controller import run_in_terminal, open_vscode
from controllers.settings_controller import open_setting
from controllers.keyboard_controller import type_text, press_key
from controllers.screen_reader_controller import read_screen, read_screen_region, analyze_screen
from controllers.form_filler_controller import fill_form, get_profile, update_profile
from controllers.window_controller import (
    wait_for_window, is_correct_window_active,
    ensure_app_focused, get_active_window_title,
    snap_window, close_window, close_all_windows,
    switch_to_window, minimize_all, list_open_windows
)
from controllers.whatsapp_controller import send_whatsapp_message, open_whatsapp
from controllers.code_controller import generate_and_run_code
from controllers.knowledge_controller import answer_question
from controllers.system_controller import get_system_info, kill_process
from controllers.utility_controller import (
    copy_screen_text, get_clipboard, get_clipboard_history, summarize_clipboard,
    copy_to_clipboard, take_screenshot, take_window_screenshot,
    open_recent_files, start_timer, get_active_timers
)
from controllers.brightness_controller import (
    set_brightness, get_brightness, brightness_up, brightness_down,
    volume_up, volume_down, mute_toggle, set_volume
)
from controllers.smart_reply_controller import smart_reply, smart_reply_and_type
from controllers.browser_playwright_controller import (
    goto as pw_goto, go_back as pw_go_back, refresh_page as pw_refresh,
    click_text as pw_click_text, click_link as pw_click_link, click_button as pw_click_button,
    click_selector as pw_click_selector,
    type_in_field as pw_type_in_field, search_on_page as pw_search_on_page,
    fill_web_form as pw_fill_web_form, submit_form as pw_submit_form,
    get_page_text as pw_get_page_text, get_page_title as pw_get_page_title,
    get_page_links as pw_get_page_links, screenshot_page as pw_screenshot_page,
    scroll_down as pw_scroll_down, scroll_up as pw_scroll_up, scroll_to_bottom as pw_scroll_to_bottom,
    new_tab as pw_new_tab, close_tab as pw_close_tab, list_tabs as pw_list_tabs,
    switch_tab as pw_switch_tab, close_browser as pw_close_browser,
)
from controllers.file_ops_controller import (
    copy_file, copy_files_by_extension, move_file, move_files_by_extension,
    rename_file, delete_file as delete_file_op, delete_files_by_pattern,
    create_folder, create_folder_structure, zip_folder, unzip_file,
    list_large_files, find_duplicates, cleanup_desktop
)
from controllers.system_maintenance_controller import (
    clear_recycle_bin, check_windows_updates, show_installed_programs,
    open_disk_cleanup, open_device_manager, check_network_speed,
    flush_dns, show_environment_variables, open_services, check_ports_in_use,
    get_startup_programs, get_disk_usage, get_wifi_info,
    shutdown_computer, cancel_shutdown, restart_computer
)
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
        name_or_path = task.get("name", task.get("path", ""))
        # If it's a full path (from a previous step like take_screenshot), open directly
        if os.path.exists(name_or_path):
            os.startfile(name_or_path)
            return f"Opened: {os.path.basename(name_or_path)}"
        return await loop.run_in_executor(None, open_file, name_or_path)

    elif tool == "open_browser":
        url = task.get("url", "https://google.com")
        # Use Playwright (CDP to user's Chrome) for all browser opens
        result = await pw_goto(url)
        return result

    elif tool == "navigate":
        url = task.get("url", "")
        return await pw_goto(url)

    elif tool == "search_web":
        query = task.get("query", "")
        return await pw_goto(f"https://www.google.com/search?q={query.replace(' ', '+')}")

    elif tool == "search_youtube":
        query = task.get("query", "")
        return await pw_search_on_page(query, "https://www.youtube.com")

    # ── Playwright Browser Tools ──────────────────────────────────────────
    elif tool == "browser_goto":
        url = task.get("url", "")
        return await pw_goto(url)

    elif tool == "browser_click":
        text = task.get("text", task.get("element", ""))
        return await pw_click_text(text)

    elif tool == "browser_click_link":
        text = task.get("text", task.get("link", ""))
        return await pw_click_link(text)

    elif tool == "browser_click_button":
        text = task.get("text", task.get("button", ""))
        return await pw_click_button(text)

    elif tool == "browser_type":
        text = task.get("text", task.get("value", ""))
        selector = task.get("selector", "")
        placeholder = task.get("placeholder", "")
        label = task.get("label", "")
        return await pw_type_in_field(text, selector, placeholder, label)

    elif tool == "browser_search":
        query = task.get("query", task.get("text", ""))
        site_url = task.get("url", "")
        return await pw_search_on_page(query, site_url)

    elif tool == "browser_fill_form":
        fields = task.get("fields", {})
        return await pw_fill_web_form(fields)

    elif tool == "browser_submit":
        return await pw_submit_form()

    elif tool == "browser_read_page":
        return await pw_get_page_text()

    elif tool == "browser_get_title":
        return await pw_get_page_title()

    elif tool == "browser_get_links":
        return await pw_get_page_links()

    elif tool == "browser_screenshot":
        name = task.get("name", "")
        return await pw_screenshot_page(name)

    elif tool == "browser_scroll_down":
        amount = int(task.get("amount", 500))
        return await pw_scroll_down(amount)

    elif tool == "browser_scroll_up":
        amount = int(task.get("amount", 500))
        return await pw_scroll_up(amount)

    elif tool == "browser_back":
        return await pw_go_back()

    elif tool == "browser_refresh":
        return await pw_refresh()

    elif tool == "browser_new_tab":
        url = task.get("url", "")
        return await pw_new_tab(url)

    elif tool == "browser_close_tab":
        return await pw_close_tab()

    elif tool == "browser_list_tabs":
        return await pw_list_tabs()

    elif tool == "browser_close":
        return await pw_close_browser()

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

    elif tool == "generate_code":
        description = task.get("description", task.get("text", ""))
        language = task.get("language", "python")
        filename = task.get("filename", "")
        return await loop.run_in_executor(None, generate_and_run_code, description, language, filename)

    elif tool == "system_info":
        query = task.get("query", "all")
        return await loop.run_in_executor(None, get_system_info, query)

    elif tool == "kill_process":
        name = task.get("name", "")
        return await loop.run_in_executor(None, kill_process, name)

    elif tool == "snap_window":
        app = task.get("app", task.get("name", ""))
        position = task.get("position", "maximize")
        return await loop.run_in_executor(None, snap_window, app, position)

    elif tool == "close_window":
        app = task.get("app", task.get("name", ""))
        return await loop.run_in_executor(None, close_window, app)

    elif tool == "close_all_windows":
        app = task.get("app", task.get("name", ""))
        return await loop.run_in_executor(None, close_all_windows, app)

    elif tool == "switch_window":
        app = task.get("app", task.get("name", ""))
        return await loop.run_in_executor(None, switch_to_window, app)

    elif tool == "minimize_all":
        return await loop.run_in_executor(None, minimize_all)

    elif tool == "list_windows":
        return await loop.run_in_executor(None, list_open_windows)

    elif tool == "copy_screen":
        return await loop.run_in_executor(None, copy_screen_text)

    elif tool == "get_clipboard":
        return await loop.run_in_executor(None, get_clipboard)

    elif tool == "clipboard_history":
        return await loop.run_in_executor(None, get_clipboard_history)

    elif tool == "summarize_clipboard":
        return await loop.run_in_executor(None, summarize_clipboard)

    elif tool == "take_screenshot":
        name = task.get("name", "")
        return await loop.run_in_executor(None, take_screenshot, name)

    elif tool == "open_recent_files":
        count = int(task.get("count", 3))
        return await loop.run_in_executor(None, open_recent_files, count)

    elif tool == "start_timer":
        seconds = int(task.get("seconds", 60))
        message = task.get("message", "Timer done!")
        return await loop.run_in_executor(None, start_timer, seconds, message)

    elif tool == "get_timers":
        return await loop.run_in_executor(None, get_active_timers)

    elif tool == "speak":
        text = task.get("text", "")
        from controllers.voice_output_controller import speak
        return await loop.run_in_executor(None, speak, text)

    elif tool == "answer_question":
        question = task.get("question", task.get("text", ""))
        # Get the answer from AI
        ai_answer = await loop.run_in_executor(None, answer_question, question)

        # If AI can't answer (real-time data), fall back to web search
        cant_answer = any(phrase in ai_answer.lower() for phrase in [
            "i'm not able to", "i cannot", "i don't have", "real-time",
            "i can't provide", "unable to", "don't have access",
            "not able to provide", "i can't access"
        ])

        if cant_answer:
            # Fall back to web search
            log.info("AI can't answer — falling back to web search")
            from controllers.voice_output_controller import speak
            speak("Let me search that for you, Sir.")
            return await search_web(question)
        else:
            # Speak the answer
            from controllers.voice_output_controller import speak
            speak(ai_answer)
            return ai_answer

    elif tool == "set_brightness":
        level = int(task.get("level", 50))
        return await loop.run_in_executor(None, set_brightness, level)

    elif tool == "brightness_up":
        return await loop.run_in_executor(None, brightness_up)

    elif tool == "brightness_down":
        return await loop.run_in_executor(None, brightness_down)

    elif tool == "volume_up":
        return await loop.run_in_executor(None, volume_up)

    elif tool == "volume_down":
        return await loop.run_in_executor(None, volume_down)

    elif tool == "mute":
        return await loop.run_in_executor(None, mute_toggle)

    elif tool == "set_volume":
        level = int(task.get("level", 50))
        return await loop.run_in_executor(None, set_volume, level)

    elif tool == "smart_reply":
        context = task.get("context", task.get("instruction", ""))
        tone = task.get("tone", "professional")
        return await loop.run_in_executor(None, smart_reply_and_type, context, tone)

    # ── File Operations ───────────────────────────────────────────────────
    elif tool == "copy_file":
        source = task.get("source", task.get("from", ""))
        destination = task.get("destination", task.get("to", ""))
        return await loop.run_in_executor(None, copy_file, source, destination)

    elif tool == "copy_files_by_type":
        ext = task.get("extension", task.get("type", ""))
        src = task.get("source", task.get("from", ""))
        dst = task.get("destination", task.get("to", ""))
        return await loop.run_in_executor(None, copy_files_by_extension, ext, src, dst)

    elif tool == "move_file":
        source = task.get("source", task.get("from", ""))
        destination = task.get("destination", task.get("to", ""))
        return await loop.run_in_executor(None, move_file, source, destination)

    elif tool == "move_files_by_type":
        ext = task.get("extension", task.get("type", ""))
        src = task.get("source", task.get("from", ""))
        dst = task.get("destination", task.get("to", ""))
        return await loop.run_in_executor(None, move_files_by_extension, ext, src, dst)

    elif tool == "rename_file":
        source = task.get("source", task.get("file", ""))
        new_name = task.get("new_name", task.get("name", ""))
        return await loop.run_in_executor(None, rename_file, source, new_name)

    elif tool == "delete_file":
        path = task.get("path", task.get("file", ""))
        return await loop.run_in_executor(None, delete_file_op, path)

    elif tool == "delete_by_pattern":
        pattern = task.get("pattern", "*.tmp")
        directory = task.get("directory", "")
        return await loop.run_in_executor(None, delete_files_by_pattern, pattern, directory)

    elif tool == "create_folder":
        name = task.get("name", "")
        directory = task.get("directory", "")
        return await loop.run_in_executor(None, create_folder, name, directory)

    elif tool == "create_folder_structure":
        folders = task.get("folders", [])
        base_dir = task.get("directory", "")
        return await loop.run_in_executor(None, create_folder_structure, folders, base_dir)

    elif tool == "zip_folder":
        source = task.get("source", task.get("path", ""))
        output = task.get("output", "")
        return await loop.run_in_executor(None, zip_folder, source, output)

    elif tool == "unzip_file":
        source = task.get("source", task.get("path", ""))
        destination = task.get("destination", "")
        return await loop.run_in_executor(None, unzip_file, source, destination)

    elif tool == "list_large_files":
        directory = task.get("directory", "")
        min_size = int(task.get("min_size_mb", 100))
        return await loop.run_in_executor(None, list_large_files, directory, min_size)

    elif tool == "find_duplicates":
        directory = task.get("directory", "")
        return await loop.run_in_executor(None, find_duplicates, directory)

    elif tool == "cleanup_desktop":
        return await loop.run_in_executor(None, cleanup_desktop)

    # ── System Maintenance ────────────────────────────────────────────────
    elif tool == "clear_recycle_bin":
        return await loop.run_in_executor(None, clear_recycle_bin)

    elif tool == "check_updates":
        return await loop.run_in_executor(None, check_windows_updates)

    elif tool == "show_installed_programs":
        return await loop.run_in_executor(None, show_installed_programs)

    elif tool == "open_disk_cleanup":
        return await loop.run_in_executor(None, open_disk_cleanup)

    elif tool == "open_device_manager":
        return await loop.run_in_executor(None, open_device_manager)

    elif tool == "check_network_speed":
        return await loop.run_in_executor(None, check_network_speed)

    elif tool == "flush_dns":
        return await loop.run_in_executor(None, flush_dns)

    elif tool == "show_env_variables":
        return await loop.run_in_executor(None, show_environment_variables)

    elif tool == "open_services":
        return await loop.run_in_executor(None, open_services)

    elif tool == "check_ports":
        return await loop.run_in_executor(None, check_ports_in_use)

    elif tool == "get_startup_programs":
        return await loop.run_in_executor(None, get_startup_programs)

    elif tool == "get_disk_usage":
        return await loop.run_in_executor(None, get_disk_usage)

    elif tool == "get_wifi_info":
        return await loop.run_in_executor(None, get_wifi_info)

    elif tool == "shutdown":
        delay = int(task.get("delay", 300))
        return await loop.run_in_executor(None, shutdown_computer, delay)

    elif tool == "cancel_shutdown":
        return await loop.run_in_executor(None, cancel_shutdown)

    elif tool == "restart":
        delay = int(task.get("delay", 60))
        return await loop.run_in_executor(None, restart_computer, delay)

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
