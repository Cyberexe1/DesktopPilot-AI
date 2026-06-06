"""
Utility Controller — clipboard, screenshots, recent files, timers.
"""

import logging
import os
import threading
import time
from datetime import datetime

import pyautogui
import pyperclip

log = logging.getLogger(__name__)

_USER = os.environ.get("USERNAME", "User")
SCREENSHOT_DIR = os.path.expanduser("~/Desktop")

# Clipboard history (in-memory, last 10 items)
_clipboard_history: list[dict] = []


# ── Clipboard ─────────────────────────────────────────────────────────────────

def copy_screen_text() -> str:
    """Read screen text via Textract and copy to clipboard."""
    from controllers.screen_reader_controller import read_screen
    text = read_screen("window")
    if text and text != "No text detected on screen":
        pyperclip.copy(text)
        _add_to_history(text)
        return f"Copied screen text to clipboard ({len(text)} chars)"
    return "No text detected on screen to copy"


def get_clipboard() -> str:
    """Get current clipboard content."""
    try:
        content = pyperclip.paste()
        if content:
            return f"Clipboard: {content[:500]}" + ("..." if len(content) > 500 else "")
        return "Clipboard is empty"
    except Exception as e:
        return f"Could not read clipboard: {e}"


def get_clipboard_history() -> str:
    """Show recent clipboard history."""
    if not _clipboard_history:
        return "No clipboard history yet"
    items = []
    for i, item in enumerate(_clipboard_history[:10], 1):
        preview = item["text"][:60] + "..." if len(item["text"]) > 60 else item["text"]
        items.append(f"{i}. [{item['time']}] {preview}")
    return "Clipboard history:\n" + "\n".join(items)


def summarize_clipboard() -> str:
    """Summarize clipboard content using AI."""
    content = pyperclip.paste()
    if not content or len(content) < 20:
        return "Clipboard is empty or too short to summarize"

    try:
        from ai.content_generator import generate_content
        summary = generate_content(
            topic=content[:500],
            content_type="summary",
            extra_instructions="Summarize this text in 2-3 bullet points. Be concise."
        )
        return f"Clipboard summary:\n{summary}"
    except Exception as e:
        # Fallback: just show first/last lines
        lines = content.strip().split('\n')
        if len(lines) > 5:
            return f"Clipboard ({len(lines)} lines): Starts with '{lines[0][:50]}...' Ends with '...{lines[-1][:50]}'"
        return f"Clipboard: {content[:200]}"


def copy_to_clipboard(text: str) -> str:
    """Copy specific text to clipboard."""
    pyperclip.copy(text)
    _add_to_history(text)
    return f"Copied to clipboard: {text[:50]}..."


def _add_to_history(text: str):
    """Add item to clipboard history."""
    _clipboard_history.insert(0, {
        "text": text,
        "time": datetime.now().strftime("%H:%M"),
    })
    if len(_clipboard_history) > 20:
        _clipboard_history.pop()


# ── Screenshot ────────────────────────────────────────────────────────────────

def take_screenshot(name: str = "") -> str:
    """Take a screenshot and save to Desktop."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name or 'screenshot'}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        log.info(f"Screenshot saved: {filepath}")
        return f"Screenshot saved: {filepath}"
    except Exception as e:
        return f"Screenshot failed: {e}"


def take_window_screenshot(name: str = "") -> str:
    """Take a screenshot of just the active window."""
    import pygetwindow as gw

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name or 'window'}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    try:
        active = gw.getActiveWindow()
        if active:
            region = (active.left, active.top, active.width, active.height)
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()

        screenshot.save(filepath)
        log.info(f"Window screenshot saved: {filepath}")
        return f"Screenshot saved: {filepath}"
    except Exception as e:
        return f"Screenshot failed: {e}"


# ── Recent Files ──────────────────────────────────────────────────────────────

def open_recent_files(count: int = 3) -> str:
    """Open the most recently modified files from Desktop/Documents/Downloads."""
    from database.sqlite_manager import get_conn

    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT name, path FROM files ORDER BY modified_date DESC LIMIT ?",
            (count,)
        ).fetchall()
        conn.close()

        if not rows:
            return "No recent files found in index"

        opened = []
        for row in rows:
            path = row["path"]
            if os.path.exists(path):
                try:
                    os.startfile(path)
                    opened.append(row["name"])
                except Exception:
                    pass

        if opened:
            return f"Opened {len(opened)} recent files: {', '.join(opened)}"
        return "Could not open any recent files"

    except Exception as e:
        return f"Failed to open recent files: {e}"


# ── Timer ─────────────────────────────────────────────────────────────────────

_active_timers: list[dict] = []


def start_timer(seconds: int, message: str = "Timer done!") -> str:
    """Start a countdown timer. Shows notification when done."""
    if seconds <= 0:
        return "Timer must be positive"
    if seconds > 3600:
        return "Timer capped at 1 hour (3600 seconds)"

    def _timer_thread():
        time.sleep(seconds)
        from controllers.notification_controller import notify
        notify("⏰ Timer", message)
        # Also speak the reminder aloud so user hears it
        try:
            from controllers.voice_output_controller import speak
            speak(f"Reminder, Sir: {message}")
        except Exception:
            pass
        log.info(f"Timer done: {message}")
        # Remove from active timers
        _active_timers[:] = [t for t in _active_timers if t["end_time"] > time.time()]

    end_time = time.time() + seconds
    timer_info = {
        "seconds": seconds,
        "message": message,
        "end_time": end_time,
        "started": datetime.now().strftime("%H:%M:%S"),
    }
    _active_timers.append(timer_info)

    thread = threading.Thread(target=_timer_thread, daemon=True)
    thread.start()

    # Format time nicely
    if seconds >= 60:
        mins = seconds // 60
        secs = seconds % 60
        time_str = f"{mins}m {secs}s" if secs else f"{mins} minutes"
    else:
        time_str = f"{seconds} seconds"

    return f"Timer started: {time_str} — will notify: '{message}'"


def get_active_timers() -> str:
    """List active timers."""
    # Clean up expired timers
    now = time.time()
    active = [t for t in _active_timers if t["end_time"] > now]
    _active_timers[:] = active

    if not active:
        return "No active timers"

    lines = []
    for t in active:
        remaining = int(t["end_time"] - now)
        mins = remaining // 60
        secs = remaining % 60
        lines.append(f"• {mins}m {secs}s remaining — '{t['message']}' (started {t['started']})")

    return f"Active timers ({len(active)}):\n" + "\n".join(lines)
