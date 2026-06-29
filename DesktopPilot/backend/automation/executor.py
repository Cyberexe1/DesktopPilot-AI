"""
Task Executor — dispatches individual tasks to controllers.
Supports multi-step chaining with automatic waits between dependent steps.

Dispatch uses a registry (HANDLERS) mapping a tool name → an async handler
function with the signature `async def handler(task, user_id, loop) -> str`.
Adding a tool = write one handler and add one entry to HANDLERS.
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
from controllers.keyboard_controller import (
    type_text, press_key, click_at,
    right_click_at, double_click_at, move_mouse, move_mouse_relative,
    scroll_at, drag_and_drop, get_mouse_position, get_screen_size,
    smart_click, smart_right_click, smart_double_click
)
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

# Tools that need time for the app/page to load before the next step runs.
# These fire ONLY before a focus-dependent tool (see TOOLS_NEEDING_FOCUS), and
# type_text/press_key have their own active-window safety check, so these are
# kept tight to reduce latency rather than padded for worst-case.
TOOLS_NEEDING_WAIT_AFTER = {
    "open_application": 1.0,   # app window
    "open_browser":     1.5,   # page load
    "open_project":     1.5,   # VS Code
    "run_terminal":     1.0,   # terminal window
    "open_file":        1.0,   # file opens in app
    "open_setting":     0.7,   # settings panel
    "navigate":         1.5,   # page navigation
    "search_web":       1.5,   # search results
    "compose_email":    1.5,   # Gmail
    "create_file":      1.0,   # file opens
    "create_project":   1.5,   # VS Code
}

# Tools that interact with the active window (need the previous step to be ready)
TOOLS_NEEDING_FOCUS = {"type_text", "press_key", "click_element", "read_screen"}


# ──────────────────────────────────────────────────────────────────────────────
# Handlers — one per tool. Signature: async def (task, user_id, loop) -> str
# ──────────────────────────────────────────────────────────────────────────────

# ── Apps / projects / files ──────────────────────────────────────────────────

async def _h_open_application(task, user_id, loop):
    name = task.get("name", "")
    result = await loop.run_in_executor(None, open_application, name)
    # Verify the app actually opened (apps usually appear within ~1-2s)
    await loop.run_in_executor(None, wait_for_window, name, 3)
    return result


async def _h_open_project(task, user_id, loop):
    project_name = task.get("project", "")
    project = find_project(project_name)
    if not project:
        return f"Project '{project_name}' not found in registry"
    result = await loop.run_in_executor(None, open_vscode, project["path"])
    await loop.run_in_executor(None, wait_for_window, "code", 5)
    update_last_project(user_id, project)
    return result


async def _h_open_file(task, user_id, loop):
    name_or_path = task.get("name", task.get("path", ""))
    # If it's a full path (from a previous step like take_screenshot), open directly
    if os.path.exists(name_or_path):
        os.startfile(name_or_path)
        return f"Opened: {os.path.basename(name_or_path)}"
    return await loop.run_in_executor(None, open_file, name_or_path)


# ── Browser (subprocess / Playwright CDP) ────────────────────────────────────

async def _h_open_browser(task, user_id, loop):
    url = task.get("url", "https://google.com")
    # Use Playwright (CDP to user's Chrome) for all browser opens
    return await pw_goto(url)


async def _h_navigate(task, user_id, loop):
    return await pw_goto(task.get("url", ""))


async def _h_search_web(task, user_id, loop):
    query = task.get("query", "")
    return await pw_goto(f"https://www.google.com/search?q={query.replace(' ', '+')}")


async def _h_search_youtube(task, user_id, loop):
    query = task.get("query", "")
    return await pw_search_on_page(query, "https://www.youtube.com")


async def _h_browser_goto(task, user_id, loop):
    return await pw_goto(task.get("url", ""))


async def _h_browser_click(task, user_id, loop):
    text = task.get("text", task.get("element", ""))
    return await pw_click_text(text)


async def _h_browser_click_link(task, user_id, loop):
    text = task.get("text", task.get("link", ""))
    return await pw_click_link(text)


async def _h_browser_click_button(task, user_id, loop):
    text = task.get("text", task.get("button", ""))
    return await pw_click_button(text)


async def _h_browser_type(task, user_id, loop):
    text = task.get("text", task.get("value", ""))
    selector = task.get("selector", "")
    placeholder = task.get("placeholder", "")
    label = task.get("label", "")
    return await pw_type_in_field(text, selector, placeholder, label)


async def _h_browser_search(task, user_id, loop):
    query = task.get("query", task.get("text", ""))
    site_url = task.get("url", "")
    return await pw_search_on_page(query, site_url)


async def _h_browser_fill_form(task, user_id, loop):
    fields = task.get("fields", {})
    return await pw_fill_web_form(fields)


async def _h_browser_submit(task, user_id, loop):
    return await pw_submit_form()


async def _h_browser_read_page(task, user_id, loop):
    return await pw_get_page_text()


async def _h_browser_get_title(task, user_id, loop):
    return await pw_get_page_title()


async def _h_browser_get_links(task, user_id, loop):
    return await pw_get_page_links()


async def _h_browser_screenshot(task, user_id, loop):
    return await pw_screenshot_page(task.get("name", ""))


async def _h_browser_scroll_down(task, user_id, loop):
    return await pw_scroll_down(int(task.get("amount", 500)))


async def _h_browser_scroll_up(task, user_id, loop):
    return await pw_scroll_up(int(task.get("amount", 500)))


async def _h_browser_back(task, user_id, loop):
    return await pw_go_back()


async def _h_browser_refresh(task, user_id, loop):
    return await pw_refresh()


async def _h_browser_new_tab(task, user_id, loop):
    return await pw_new_tab(task.get("url", ""))


async def _h_browser_close_tab(task, user_id, loop):
    return await pw_close_tab()


async def _h_browser_list_tabs(task, user_id, loop):
    return await pw_list_tabs()


async def _h_browser_close(task, user_id, loop):
    return await pw_close_browser()


# ── Waits / terminal / settings / email ──────────────────────────────────────

async def _h_wait(task, user_id, loop):
    # Explicit wait — user or AI requested a pause
    seconds = float(task.get("seconds", task.get("duration", 2)))
    seconds = min(seconds, 30)  # Cap at 30s for safety
    log.info(f"Waiting {seconds}s...")
    await asyncio.sleep(seconds)
    return f"Waited {seconds} seconds"


async def _h_wait_for_server(task, user_id, loop):
    url = task.get("url", "http://localhost:8000")
    return await loop.run_in_executor(None, _wait_for_server, url)


async def _h_run_terminal(task, user_id, loop):
    command = task.get("command", "")
    project_name = task.get("project", "")
    project = find_project(project_name) if project_name else None
    cwd = project["path"] if project else None
    return await loop.run_in_executor(None, run_in_terminal, command, cwd)


async def _h_open_setting(task, user_id, loop):
    return await loop.run_in_executor(None, open_setting, task.get("name", ""))


async def _h_compose_email(task, user_id, loop):
    result = await open_gmail_compose(
        task.get("to", ""),
        task.get("subject", ""),
        task.get("body", ""),
    )
    # Wait for browser/Gmail to open
    await loop.run_in_executor(None, wait_for_window, "mail", 5)
    return result


# ── Keyboard / focus-dependent ────────────────────────────────────────────────

async def _h_type_text(task, user_id, loop):
    text = task.get("text", "")
    # Safety check: verify something meaningful is in focus
    active_title = await loop.run_in_executor(None, get_active_window_title)
    if not active_title or active_title.lower() in ["", "desktop", "taskbar"]:
        return "Cannot type — no application window is in focus. Open an app first."
    log.info(f"Typing into: '{active_title}'")
    return await loop.run_in_executor(None, type_text, text)


async def _h_press_key(task, user_id, loop):
    key = task.get("key", "")
    active_title = await loop.run_in_executor(None, get_active_window_title)
    if not active_title:
        return "Cannot press key — no window in focus"
    return await loop.run_in_executor(None, press_key, key)


async def _h_click_element(task, user_id, loop):
    # Click at coordinates or use screen reading to find element
    x = int(task.get("x", 0))
    y = int(task.get("y", 0))
    return await loop.run_in_executor(None, click_at, x, y)


# ── Advanced mouse controls ───────────────────────────────────────────────────

async def _h_right_click(task, user_id, loop):
    x = task.get("x")
    y = task.get("y")
    args = [int(x), int(y)] if x is not None and y is not None else []
    return await loop.run_in_executor(None, right_click_at, *args)


async def _h_double_click(task, user_id, loop):
    x = task.get("x")
    y = task.get("y")
    args = [int(x), int(y)] if x is not None and y is not None else []
    return await loop.run_in_executor(None, double_click_at, *args)


async def _h_move_mouse(task, user_id, loop):
    x = int(task.get("x", 0))
    y = int(task.get("y", 0))
    duration = float(task.get("duration", 0.3))
    return await loop.run_in_executor(None, move_mouse, x, y, duration)


async def _h_scroll(task, user_id, loop):
    x = task.get("x")
    y = task.get("y")
    amount = int(task.get("amount", 3))
    direction = task.get("direction", "down")
    if x is not None and y is not None:
        return await loop.run_in_executor(None, scroll_at, int(x), int(y), amount, direction)
    return await loop.run_in_executor(None, scroll_at, None, None, amount, direction)


async def _h_drag_drop(task, user_id, loop):
    return await loop.run_in_executor(
        None, drag_and_drop,
        int(task.get("from_x", 0)), int(task.get("from_y", 0)),
        int(task.get("to_x", 0)), int(task.get("to_y", 0)),
    )


async def _h_get_mouse_position(task, user_id, loop):
    return await loop.run_in_executor(None, get_mouse_position)


async def _h_smart_click(task, user_id, loop):
    text = task.get("text", task.get("label", ""))
    return await loop.run_in_executor(None, smart_click, text, "left")


async def _h_smart_right_click(task, user_id, loop):
    text = task.get("text", task.get("label", ""))
    return await loop.run_in_executor(None, smart_right_click, text)


async def _h_smart_double_click(task, user_id, loop):
    text = task.get("text", task.get("label", ""))
    return await loop.run_in_executor(None, smart_double_click, text)


# ── File writing / projects ───────────────────────────────────────────────────

async def _h_create_file(task, user_id, loop):
    filename  = task.get("filename", "")
    content   = task.get("content", "")
    directory = task.get("directory", "")
    # Optional slide count for .pptx (planner extracts "N slides" from the command)
    try:
        slides = int(task.get("slides", 0) or 0)
    except (TypeError, ValueError):
        slides = 0
    return await loop.run_in_executor(None, create_file, filename, content, directory, slides)


async def _h_write_to_file(task, user_id, loop):
    filepath = task.get("filepath", "")
    content  = task.get("content", "")
    return await loop.run_in_executor(None, write_to_file, filepath, content)


async def _h_create_project(task, user_id, loop):
    name      = task.get("name", task.get("project", ""))
    framework = task.get("framework", "html")
    directory = task.get("directory", "")
    return await loop.run_in_executor(None, create_project, name, framework, directory)


# ── Screen / profile / forms ──────────────────────────────────────────────────

async def _h_read_screen(task, user_id, loop):
    mode = task.get("mode", "full")
    return await loop.run_in_executor(None, read_screen, mode)


async def _h_analyze_screen(task, user_id, loop):
    result = await loop.run_in_executor(None, analyze_screen)
    return f"Screen text ({result['line_count']} lines):\n{result['text'][:500]}"


async def _h_fill_form(task, user_id, loop):
    return await loop.run_in_executor(None, fill_form)


async def _h_set_profile(task, user_id, loop):
    field = task.get("field", "")
    value = task.get("value", "")
    return await loop.run_in_executor(None, update_profile, field, value)


async def _h_get_profile(task, user_id, loop):
    profile = get_profile()
    filled = {k: v for k, v in profile.items() if v}
    return f"Profile: {json.dumps(filled, indent=2)}" if filled else "Profile is empty"


# ── WhatsApp / code / system ──────────────────────────────────────────────────

async def _h_send_whatsapp(task, user_id, loop):
    contact = task.get("contact", task.get("to", ""))
    message = task.get("message", task.get("text", ""))
    return await send_whatsapp_message(contact, message)


async def _h_open_whatsapp(task, user_id, loop):
    return await open_whatsapp()


async def _h_generate_code(task, user_id, loop):
    description = task.get("description", task.get("text", ""))
    language = task.get("language", "python")
    filename = task.get("filename", "")
    return await loop.run_in_executor(None, generate_and_run_code, description, language, filename)


async def _h_system_info(task, user_id, loop):
    query = task.get("query", "all")
    return await loop.run_in_executor(None, get_system_info, query)


async def _h_kill_process(task, user_id, loop):
    return await loop.run_in_executor(None, kill_process, task.get("name", ""))


# ── Windows ───────────────────────────────────────────────────────────────────

async def _h_snap_window(task, user_id, loop):
    app = task.get("app", task.get("name", ""))
    position = task.get("position", "maximize")
    return await loop.run_in_executor(None, snap_window, app, position)


async def _h_close_window(task, user_id, loop):
    app = task.get("app", task.get("name", ""))
    return await loop.run_in_executor(None, close_window, app)


async def _h_close_all_windows(task, user_id, loop):
    app = task.get("app", task.get("name", ""))
    return await loop.run_in_executor(None, close_all_windows, app)


async def _h_switch_window(task, user_id, loop):
    app = task.get("app", task.get("name", ""))
    return await loop.run_in_executor(None, switch_to_window, app)


async def _h_minimize_all(task, user_id, loop):
    return await loop.run_in_executor(None, minimize_all)


async def _h_list_windows(task, user_id, loop):
    return await loop.run_in_executor(None, list_open_windows)


# ── Clipboard / utilities ─────────────────────────────────────────────────────

async def _h_copy_screen(task, user_id, loop):
    return await loop.run_in_executor(None, copy_screen_text)


async def _h_get_clipboard(task, user_id, loop):
    return await loop.run_in_executor(None, get_clipboard)


async def _h_clipboard_history(task, user_id, loop):
    # NOTE: preserves original if/elif first-match behavior (utility_controller).
    return await loop.run_in_executor(None, get_clipboard_history)


async def _h_summarize_clipboard(task, user_id, loop):
    return await loop.run_in_executor(None, summarize_clipboard)


async def _h_take_screenshot(task, user_id, loop):
    return await loop.run_in_executor(None, take_screenshot, task.get("name", ""))


async def _h_open_recent_files(task, user_id, loop):
    count = int(task.get("count", 3))
    return await loop.run_in_executor(None, open_recent_files, count)


async def _h_start_timer(task, user_id, loop):
    seconds = int(task.get("seconds", 60))
    message = task.get("message", "Timer done!")
    return await loop.run_in_executor(None, start_timer, seconds, message)


async def _h_get_timers(task, user_id, loop):
    return await loop.run_in_executor(None, get_active_timers)


# ── Speech / Q&A ──────────────────────────────────────────────────────────────

async def _h_speak(task, user_id, loop):
    text = task.get("text", "")
    from controllers.voice_output_controller import speak
    return await loop.run_in_executor(None, speak, text)


async def _h_answer_question(task, user_id, loop):
    question = task.get("question") or task.get("text") or task.get("query") or ""
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


# ── Brightness / volume ───────────────────────────────────────────────────────

async def _h_set_brightness(task, user_id, loop):
    level = int(task.get("level", 50))
    return await loop.run_in_executor(None, set_brightness, level)


async def _h_brightness_up(task, user_id, loop):
    return await loop.run_in_executor(None, brightness_up)


async def _h_brightness_down(task, user_id, loop):
    return await loop.run_in_executor(None, brightness_down)


async def _h_volume_up(task, user_id, loop):
    return await loop.run_in_executor(None, volume_up)


async def _h_volume_down(task, user_id, loop):
    return await loop.run_in_executor(None, volume_down)


async def _h_mute(task, user_id, loop):
    return await loop.run_in_executor(None, mute_toggle)


async def _h_set_volume(task, user_id, loop):
    level = int(task.get("level", 50))
    return await loop.run_in_executor(None, set_volume, level)


async def _h_smart_reply(task, user_id, loop):
    context = task.get("context", task.get("instruction", ""))
    tone = task.get("tone", "professional")
    return await loop.run_in_executor(None, smart_reply_and_type, context, tone)


# ── File operations ───────────────────────────────────────────────────────────

async def _h_copy_file(task, user_id, loop):
    source = task.get("source", task.get("from", ""))
    destination = task.get("destination", task.get("to", ""))
    return await loop.run_in_executor(None, copy_file, source, destination)


async def _h_copy_files_by_type(task, user_id, loop):
    ext = task.get("extension", task.get("type", ""))
    src = task.get("source", task.get("from", ""))
    dst = task.get("destination", task.get("to", ""))
    return await loop.run_in_executor(None, copy_files_by_extension, ext, src, dst)


async def _h_move_file(task, user_id, loop):
    source = task.get("source", task.get("from", ""))
    destination = task.get("destination", task.get("to", ""))
    return await loop.run_in_executor(None, move_file, source, destination)


async def _h_move_files_by_type(task, user_id, loop):
    ext = task.get("extension", task.get("type", ""))
    src = task.get("source", task.get("from", ""))
    dst = task.get("destination", task.get("to", ""))
    return await loop.run_in_executor(None, move_files_by_extension, ext, src, dst)


async def _h_rename_file(task, user_id, loop):
    source = task.get("source", task.get("file", ""))
    new_name = task.get("new_name", task.get("name", ""))
    return await loop.run_in_executor(None, rename_file, source, new_name)


async def _h_delete_file(task, user_id, loop):
    path = task.get("path", task.get("file", ""))
    return await loop.run_in_executor(None, delete_file_op, path)


async def _h_delete_by_pattern(task, user_id, loop):
    pattern = task.get("pattern", "*.tmp")
    directory = task.get("directory", "")
    return await loop.run_in_executor(None, delete_files_by_pattern, pattern, directory)


async def _h_create_folder(task, user_id, loop):
    name = task.get("name", "")
    directory = task.get("directory", "")
    return await loop.run_in_executor(None, create_folder, name, directory)


async def _h_create_folder_structure(task, user_id, loop):
    folders = task.get("folders", [])
    base_dir = task.get("directory", "")
    return await loop.run_in_executor(None, create_folder_structure, folders, base_dir)


async def _h_zip_folder(task, user_id, loop):
    source = task.get("source", task.get("path", ""))
    output = task.get("output", "")
    return await loop.run_in_executor(None, zip_folder, source, output)


async def _h_unzip_file(task, user_id, loop):
    source = task.get("source", task.get("path", ""))
    destination = task.get("destination", "")
    return await loop.run_in_executor(None, unzip_file, source, destination)


async def _h_list_large_files(task, user_id, loop):
    directory = task.get("directory", "")
    min_size = int(task.get("min_size_mb", 100))
    return await loop.run_in_executor(None, list_large_files, directory, min_size)


async def _h_find_duplicates(task, user_id, loop):
    return await loop.run_in_executor(None, find_duplicates, task.get("directory", ""))


async def _h_cleanup_desktop(task, user_id, loop):
    return await loop.run_in_executor(None, cleanup_desktop)


# ── System maintenance ────────────────────────────────────────────────────────

async def _h_clear_recycle_bin(task, user_id, loop):
    return await loop.run_in_executor(None, clear_recycle_bin)


async def _h_check_updates(task, user_id, loop):
    return await loop.run_in_executor(None, check_windows_updates)


async def _h_show_installed_programs(task, user_id, loop):
    return await loop.run_in_executor(None, show_installed_programs)


async def _h_open_disk_cleanup(task, user_id, loop):
    return await loop.run_in_executor(None, open_disk_cleanup)


async def _h_open_device_manager(task, user_id, loop):
    return await loop.run_in_executor(None, open_device_manager)


async def _h_check_network_speed(task, user_id, loop):
    return await loop.run_in_executor(None, check_network_speed)


async def _h_flush_dns(task, user_id, loop):
    return await loop.run_in_executor(None, flush_dns)


async def _h_show_env_variables(task, user_id, loop):
    return await loop.run_in_executor(None, show_environment_variables)


async def _h_open_services(task, user_id, loop):
    return await loop.run_in_executor(None, open_services)


async def _h_check_ports(task, user_id, loop):
    return await loop.run_in_executor(None, check_ports_in_use)


async def _h_get_startup_programs(task, user_id, loop):
    return await loop.run_in_executor(None, get_startup_programs)


async def _h_get_disk_usage(task, user_id, loop):
    return await loop.run_in_executor(None, get_disk_usage)


async def _h_get_wifi_info(task, user_id, loop):
    return await loop.run_in_executor(None, get_wifi_info)


async def _h_shutdown(task, user_id, loop):
    delay = int(task.get("delay", 300))
    return await loop.run_in_executor(None, shutdown_computer, delay)


async def _h_cancel_shutdown(task, user_id, loop):
    return await loop.run_in_executor(None, cancel_shutdown)


async def _h_restart(task, user_id, loop):
    delay = int(task.get("delay", 60))
    return await loop.run_in_executor(None, restart_computer, delay)


# ── Meeting assistant ─────────────────────────────────────────────────────────

async def _h_start_meeting(task, user_id, loop):
    from controllers.meeting_controller import start_meeting
    title = task.get("title", task.get("name", ""))
    return await loop.run_in_executor(None, start_meeting, title)


async def _h_stop_meeting(task, user_id, loop):
    from controllers.meeting_controller import stop_meeting, process_meeting
    stop_result = stop_meeting()
    if "error" in stop_result:
        return stop_result["error"]
    email = task.get("email", "")
    result = await process_meeting(
        stop_result["wav_path"], stop_result["title"], email
    )
    items = len(result.get("action_items", []))
    doc   = os.path.basename(result.get("doc_path", "notes.docx"))
    return f"Meeting notes created: {doc} — {items} action items extracted"


# ── Clipboard manager ─────────────────────────────────────────────────────────

async def _h_clipboard_query(task, user_id, loop):
    from controllers.clipboard_manager_controller import ai_clipboard_query
    query = task.get("query", task.get("text", ""))
    return await loop.run_in_executor(None, ai_clipboard_query, query)


async def _h_paste_clip(task, user_id, loop):
    from controllers.clipboard_manager_controller import paste_clip
    entry_id = int(task.get("id", 1))
    return await loop.run_in_executor(None, paste_clip, entry_id)


# ── Focus mode ────────────────────────────────────────────────────────────────

async def _h_start_focus(task, user_id, loop):
    from controllers.focus_controller import start_focus_mode
    hours  = float(task.get("hours", task.get("duration_hours", 2.0)))
    goal   = task.get("goal", "")
    f_min  = int(task.get("focus_min", 25))
    b_min  = int(task.get("break_min", 5))
    return await loop.run_in_executor(None, start_focus_mode, hours, goal, f_min, b_min)


async def _h_stop_focus(task, user_id, loop):
    from controllers.focus_controller import stop_focus_mode
    result = await loop.run_in_executor(None, stop_focus_mode)
    if "error" in result:
        return result["error"]
    return (
        f"Focus session ended — {result['cycles_completed']} cycles, "
        f"{result['total_focus_min']} minutes focused. "
        f"Efficiency: {result['efficiency']}"
    )


async def _h_focus_status(task, user_id, loop):
    from controllers.focus_controller import get_focus_status
    status = get_focus_status()
    if not status["active"]:
        return "Focus mode is not active"
    remaining = status["remaining_sec"]
    mins = remaining // 60
    secs = remaining % 60
    return (
        f"Focus mode: Cycle {status['cycle']}/{status['total_cycles']} — "
        f"{status['mode'].upper()} — {mins}m {secs}s remaining"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Registry — tool name → handler
# ──────────────────────────────────────────────────────────────────────────────

HANDLERS = {
    # apps / projects / files
    "open_application":        _h_open_application,
    "open_project":            _h_open_project,
    "open_file":               _h_open_file,
    "open_folder":             _h_open_file,   # alias — open a folder the same way
    # browser
    "open_browser":            _h_open_browser,
    "navigate":                _h_navigate,
    "search_web":              _h_search_web,
    "search_youtube":          _h_search_youtube,
    "browser_goto":            _h_browser_goto,
    "browser_click":           _h_browser_click,
    "browser_click_link":      _h_browser_click_link,
    "browser_click_button":    _h_browser_click_button,
    "browser_type":            _h_browser_type,
    "browser_search":          _h_browser_search,
    "browser_fill_form":       _h_browser_fill_form,
    "browser_submit":          _h_browser_submit,
    "browser_read_page":       _h_browser_read_page,
    "browser_get_title":       _h_browser_get_title,
    "browser_get_links":       _h_browser_get_links,
    "browser_screenshot":      _h_browser_screenshot,
    "browser_scroll_down":     _h_browser_scroll_down,
    "browser_scroll_up":       _h_browser_scroll_up,
    "browser_back":            _h_browser_back,
    "browser_refresh":         _h_browser_refresh,
    "browser_new_tab":         _h_browser_new_tab,
    "browser_close_tab":       _h_browser_close_tab,
    "browser_list_tabs":       _h_browser_list_tabs,
    "browser_close":           _h_browser_close,
    # waits / terminal / settings / email
    "wait":                    _h_wait,
    "wait_for_server":         _h_wait_for_server,
    "run_terminal":            _h_run_terminal,
    "open_setting":            _h_open_setting,
    "compose_email":           _h_compose_email,
    # keyboard / focus-dependent
    "type_text":               _h_type_text,
    "press_key":               _h_press_key,
    "click_element":           _h_click_element,
    # advanced mouse
    "right_click":             _h_right_click,
    "double_click":            _h_double_click,
    "move_mouse":              _h_move_mouse,
    "scroll":                  _h_scroll,
    "drag_drop":               _h_drag_drop,
    "get_mouse_position":      _h_get_mouse_position,
    "smart_click":             _h_smart_click,
    "smart_right_click":       _h_smart_right_click,
    "smart_double_click":      _h_smart_double_click,
    # file writing / projects
    "create_file":             _h_create_file,
    "write_to_file":           _h_write_to_file,
    "create_project":          _h_create_project,
    # screen / profile / forms
    "read_screen":             _h_read_screen,
    "analyze_screen":          _h_analyze_screen,
    "fill_form":               _h_fill_form,
    "set_profile":             _h_set_profile,
    "get_profile":             _h_get_profile,
    # whatsapp / code / system
    "send_whatsapp":           _h_send_whatsapp,
    "open_whatsapp":           _h_open_whatsapp,
    "generate_code":           _h_generate_code,
    "system_info":             _h_system_info,
    "kill_process":            _h_kill_process,
    # windows
    "snap_window":             _h_snap_window,
    "close_window":            _h_close_window,
    "close_all_windows":       _h_close_all_windows,
    "switch_window":           _h_switch_window,
    "minimize_all":            _h_minimize_all,
    "list_windows":            _h_list_windows,
    # clipboard / utilities
    "copy_screen":             _h_copy_screen,
    "get_clipboard":           _h_get_clipboard,
    "clipboard_history":       _h_clipboard_history,
    "summarize_clipboard":     _h_summarize_clipboard,
    "take_screenshot":         _h_take_screenshot,
    "open_recent_files":       _h_open_recent_files,
    "start_timer":             _h_start_timer,
    "get_timers":              _h_get_timers,
    # speech / Q&A
    "speak":                   _h_speak,
    "answer_question":         _h_answer_question,
    # brightness / volume
    "set_brightness":          _h_set_brightness,
    "brightness_up":           _h_brightness_up,
    "brightness_down":         _h_brightness_down,
    "volume_up":               _h_volume_up,
    "volume_down":             _h_volume_down,
    "mute":                    _h_mute,
    "set_volume":              _h_set_volume,
    "smart_reply":             _h_smart_reply,
    # file operations
    "copy_file":               _h_copy_file,
    "copy_files_by_type":      _h_copy_files_by_type,
    "move_file":               _h_move_file,
    "move_files_by_type":      _h_move_files_by_type,
    "rename_file":             _h_rename_file,
    "delete_file":             _h_delete_file,
    "delete_by_pattern":       _h_delete_by_pattern,
    "create_folder":           _h_create_folder,
    "create_folder_structure": _h_create_folder_structure,
    "zip_folder":              _h_zip_folder,
    "unzip_file":              _h_unzip_file,
    "list_large_files":        _h_list_large_files,
    "find_duplicates":         _h_find_duplicates,
    "cleanup_desktop":         _h_cleanup_desktop,
    # system maintenance
    "clear_recycle_bin":       _h_clear_recycle_bin,
    "check_updates":           _h_check_updates,
    "show_installed_programs": _h_show_installed_programs,
    "open_disk_cleanup":       _h_open_disk_cleanup,
    "open_device_manager":     _h_open_device_manager,
    "check_network_speed":     _h_check_network_speed,
    "flush_dns":               _h_flush_dns,
    "show_env_variables":      _h_show_env_variables,
    "open_services":           _h_open_services,
    "check_ports":             _h_check_ports,
    "get_startup_programs":    _h_get_startup_programs,
    "get_disk_usage":          _h_get_disk_usage,
    "get_wifi_info":           _h_get_wifi_info,
    "shutdown":                _h_shutdown,
    "cancel_shutdown":         _h_cancel_shutdown,
    "restart":                 _h_restart,
    # meeting assistant
    "start_meeting":           _h_start_meeting,
    "stop_meeting":            _h_stop_meeting,
    # clipboard manager
    "clipboard_query":         _h_clipboard_query,
    "paste_clip":              _h_paste_clip,
    # focus mode
    "start_focus":             _h_start_focus,
    "stop_focus":              _h_stop_focus,
    "focus_status":            _h_focus_status,
}


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

    handler = HANDLERS.get(tool)
    if handler is None:
        return f"Unknown tool: {tool}"
    return await handler(task, user_id, loop)


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
